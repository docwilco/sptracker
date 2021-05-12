# -*- coding: utf-8 -*-

# Copyright 2015-2016 NEYS
# This file is part of sptracker.
#
#    sptracker is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    sptracker is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Foobar.  If not, see <http://www.gnu.org/licenses/>.


from collections import OrderedDict
import math
import os
import pickle
import re
import shutil
import sys
import time
import traceback

from threading import RLock
from urllib.parse import urlparse, parse_qsl

from stracker_lib import config
from stracker_lib.logger import *
from stracker_lib import version

from ptracker_lib.dbgeneric import decompress
from ptracker_lib.helpers import isProMode, format_time_ms, format_datetime, unixtime2datetime, datetime2unixtime, format_time, localtime2utc, utc2localtime, unixtime_now, format_time_s, setFormatUnits
from ptracker_lib import read_ui_data

import simplejson as json

import bottle
import cherrypy

# avoid css system override (can be caused by installing Dreamweaver, http://stackoverflow.com/questions/22839278/python-built-in-server-not-loading-css)
import mimetypes
mimetypes.add_type("text/css", ".css", True)

dirs = [
    "apps/python/ptracker",
    ".",
    "..",
    os.path.split(sys.argv[0])[0],
    os.path.join(os.path.split(sys.argv[0])[0], ".."),
    os.path.join(os.path.split(sys.argv[0])[0], "..", "."),
    os.path.join(os.path.split(sys.argv[0])[0], "..", "..", ".."),
    os.path.split(__file__)[0],
    os.path.join(os.path.split(__file__)[0], ".."),
    os.path.join(os.path.split(__file__)[0], "..", ".."),
    os.path.join(os.path.split(__file__)[0], "..", "..", ".."),
]
for d in dirs:
    if os.path.isdir(os.path.join(d, "http_static")):
        static_base_dir = d
        break
sys.path.append(static_base_dir)

from http_templates import tmpl_helpers
from http_templates.tmpl_base import baseTemplate
from http_templates.tmpl_laptimes import lapStatTableTemplate, lapDetailsTableTemplate
from http_templates.tmpl_players import playersTemplate, plyDetailsTemplate
from http_templates.tmpl_sessions import sesStatTableTemplate, sesDetailsTemplate, pisDetailsTemplate
from http_templates.tmpl_mainpage import mainPageTemplate
from http_templates.tmpl_championship import championshipTemplate
from http_templates.tmpl_statistics import statisticsTemplate

db = None

class StrackerPublicBase:
    def __init__(self):
        self.rootpage = '/'
        self.static_base_dir = static_base_dir
        dest = os.path.abspath(os.path.join(static_base_dir, "http_static", "img", "banner.png"))
        try:
            shutil.copyfile(config.config.HTTP_CONFIG.banner, dest)
        except:
            src = os.path.abspath(os.path.join(static_base_dir, "http_static", "img",
"assettocorsa.png"))
            shutil.copyfile(src, dest)
        self.itemsPerPage = min(150, max(2, config.config.HTTP_CONFIG.items_per_page))
        self.lastStat = None
        self._trackAndCarDetails = None
        self.streamingClientsCount = 0
        self.trackAndCarLock = RLock()
        self.resetTrackAndCarDetails()
        setFormatUnits("km/h" if config.config.HTTP_CONFIG.velocity_unit == config.config.VU_KMH else "mph",
                       "°C" if config.config.HTTP_CONFIG.temperature_unit == config.config.TU_DEGC else "°F")

    def isAdmin(self):
        return None

    def features(self):
        return {'admin': self.isAdmin(),
                'banlist': False,
                'version': version,
                'checksum_tests': config.config.STRACKER_CONFIG.perform_checksum_comparisons,
                'pts':True,
                }

    def toTimestamp(self, date, off=0):
        if date is None:
            return (None, "")
        M = re.match('([0-9]{4})-([0-9]{2})-([0-9]{2})', date)
        if not M is None:
            year = int(M.group(1))
            month = int(M.group(2))
            day = int(M.group(3))
            dt = datetime.datetime(year, month, day)
            dt = localtime2utc(dt)
            return (datetime2unixtime(dt)+off, date)
        return (None,"")

    def trackAndCarDetails(self):
        with self.trackAndCarLock:
            if self._trackAndCarDetails is None or time.time()-self._trackAndCarDetailsTS > 60*30:
                self.resetTrackAndCarDetails()
            return self._trackAndCarDetails

    def resetTrackAndCarDetails(self):
        with self.trackAndCarLock:
            self._trackAndCarDetails = db.trackAndCarDetails(__sync=True)()
            if self.features()['pts']:
                trackres = []
                carres = []
                for ci in self._trackAndCarDetails['tracks']:
                    if ci['uiname'] is None or ci['mapdata'] is None:
                        updated = False
                        data = {'tracks' : {ci['acname'] : {}}}
                        try:
                            for f in read_ui_data.track_files(ci['acname'], "."):
                                if f is not None:
                                    try:
                                        data = read_ui_data.read_ui_file(f, open(f, "rb"), data)
                                    except:
                                        acdump("Exception in add ui track 0: %s", traceback.format_exc())
                            td = data['tracks'][ci['acname']]
                            uiname = td.get('uiname', None)
                            if ci['uiname'] not in [None, ci['acname']] and not uiname is None:
                                ci['uiname'] = uiname
                                acdebug("Setting uiname of %s to %s", ci['acname'], ci['uiname'])
                                updated = True
                            if ci['mapdata'] is None and 'mini' in td and 'mpng' in td:
                                mapdata = dict(ini=td['mini'], png=td['mpng'])
                                if 'sections' in td:
                                    mapdata['sections'] = td['sections']
                                else:
                                    acwarning("no sections for %s", ci['acname'])
                                ci['mapdata'] = pickle.dumps(mapdata)
                                acdebug("Setting mapdata of %s", ci['acname'])
                                updated = True
                        except:
                            acdump("Exception in add ui track 1: %s", traceback.format_exc())
                        if updated:
                            td = {'track':ci['acname']}
                            td.update(ci)
                            trackres.append(td)
                for ci in self._trackAndCarDetails['cars']:
                    if ci['uiname'] is None or ci['brand'] is None:
                        updated = False
                        data = {'cars' : {ci['acname']: {}}}
                        try:
                            for f in read_ui_data.car_files(ci["acname"], "."):
                                try:
                                    data = read_ui_data.read_ui_file(f, open(f, "rb"), data)
                                except:
                                    acdump("Exception in add ui car 0: %s", traceback.format_exc())
                            uiname = data['cars'][ci['acname']].get('uiname', None)
                            if ci['uiname'] is None and not uiname is None:
                                ci['uiname'] = uiname
                                acdebug("Setting uiname of %s to %s", ci['acname'], ci['uiname'])
                                updated = True
                            brand = data['cars'][ci['acname']].get('brand', None)
                            if ci['brand'] is None and not brand is None:
                                ci['brand'] = brand
                                acdebug("Setting brand of %s to %s", ci['acname'], ci["brand"])
                                updated = True
                            badge = data['cars'][ci['acname']].get('badge', None)
                            if ci['badge'] is None and not badge is None:
                                ci['badge'] = badge
                                acdebug("Setting badge of %s", ci['acname'])
                                updated = True
                        except:
                            acdump("Exception in add ui car 1: %s", traceback.format_exc())
                        if updated:
                            cd = {'car' : ci['acname']}
                            cd.update(ci)
                            carres.append(cd)
                if len(trackres) > 0 or len(carres) > 0:
                    acdebug("Adding additional track and car details")
                    self._trackAndCarDetails = db.trackAndCarDetails(__sync=True,tracks=trackres,cars=carres)()
            tmpl_helpers.set_car_info(dict(map(lambda x: (x['acname'], x), self._trackAndCarDetails['cars'])))
            self._trackAndCarDetailsTS = time.time()

    def lapstat(self, track = None, cars = None, page = 0, valid = None, date_from = None, date_to = None, tyres = None, currservers = None, ranking = None, groups = None, curr_url=None):
        if not currservers is None:
            currservers = currservers.split(",")
            server = currservers[0] if len(currservers) else None
        else:
            server = None
        ccTrack, ccCars = db.currentCombo(__sync=True, server=server)()
        currtrack = track
        currcars = cars
        if currtrack is None:
            currtrack = ccTrack
        if currcars is None:
            currcars = ccCars
        else:
            currcars = currcars.split(",")
        if not valid is None:
            try:
                valid = set(map(int, valid.split(",")))
            except ValueError:
                valid = set([1,2])
        else:
            valid = set([1,2])
        if ranking is None:
            ranking = 0
        else:
            ranking = int(ranking)
        if groups is None:
            groups = []
        else:
            groups = [int(x) for x in groups.split(",")]
        allgroups = db.allgroups(__sync=True)()
        date_from = self.toTimestamp(date_from)
        date_to = self.toTimestamp(date_to, 24*60*60)
        try:
            page = int(page)
        except TypeError as e:
            acerror("Caught type error while converting lapstat page argument")
            acerror("  page=%s", repr(page))
            raise(e)
        tracks = sorted(db.alltracks(__sync=True)(), key=lambda x: x['uitrack'])
        cars = sorted(db.allcars(__sync=True)(), key=lambda x: x['uicar'])
        servers = sorted(db.allservers(__sync=True)())
        if not tyres is None:
            tyre_list = tyres.split(",")
        else:
            tyre_list = None
        nip = self.itemsPerPage
        res = db.lapStats(__sync=True,
                          mode="top-extended",
                          limit=[page*nip+1,nip],
                          track=currtrack,
                          cars = currcars,
                          ego_guid = None,
                          valid = list(valid),
                          tyre_list = tyre_list,
                          minSessionStartTime = [date_from[0], date_to[0]],
                          artint=0,
                          server=server,
                          group_by_guid=ranking,
                          groups=groups)()
        if not res is None:
            count = 0
            for i,s in enumerate(res['bestSectors']):
                if not s is None:
                    count = i+1
            totalPages=(res['totalNumLaps']+nip-1)//nip
            lapStatRes = res['laps']
            bestSectors = res['bestSectors']
        else:
            totalPages = 1
            count = 0
            lapStatRes = []
            bestSectors = []
        r = lapStatTableTemplate.render(lapStatRes=lapStatRes,
                                        bestSectors=bestSectors,
                                        count=count,
                                        tracks=tracks,
                                        cars=cars,
                                        currtrack=currtrack,
                                        currcars=currcars,
                                        valid=valid,
                                        date_from=date_from,
                                        date_to=date_to,
                                        tyres=tyres,
                                        currservers=currservers,
                                        servers=servers,
                                        ranking=ranking,
                                        currgroups=groups,
                                        groups=allgroups,
                                        features=self.features())
        return baseTemplate.render(base=r, pagination=(page, totalPages), src="lapstat", rootpage=self.rootpage, features=self.features(), curr_url=curr_url)

    def lapdetails(self, lapid, cmpbits=None, cmp_lapid=None, curr_url=None):
        lapid = int(lapid)
        cmpbits = cmpbits if cmpbits is None else int(cmpbits)
        details = db.lapDetails(__sync=True, lapid=lapid, withHistoryInfo=True)()
        r = lapDetailsTableTemplate.render(lapdetails=details, cmpbits=cmpbits, features=self.features(), http_server=self, cmp_lapid=cmp_lapid, curr_url=curr_url)
        return baseTemplate.render(base=r, pagination=None, src="lapstat", rootpage=self.rootpage, features=self.features(), curr_url=curr_url)

    def sessionstat(self, track = "(all)", page = 0, start = None, stop = None, session_types = None, num_players = None, num_laps = None, curr_url=None):
        tracks = [dict(track="(all)",uitrack="(all)")] + sorted(db.alltracks(__sync=True)(), key=lambda x: x['uitrack'])
        currtrack = track
        from_time = self.toTimestamp(start)
        to_time = self.toTimestamp(stop,24*60*60) # to should be inclusive
        page = int(page)
        nip = self.itemsPerPage
        if session_types == None:
            session_types = "Practice,Race,Qualify"
        session_types = session_types.split(",")
        if num_players is None:
            num_players = 0
        num_players = int(num_players)
        if num_laps is None:
            num_laps = 0
        num_laps = int(num_laps)

        res = db.sessionStats(__sync=True,
                              limit=[page*nip+1, nip],
                              tracks = None if currtrack == "(all)" else currtrack,
                              sessionTypes = session_types,
                              ego_guid = None,
                              minSessionStartTime = [from_time[0], to_time[0]],
                              minNumPlayers = num_players,
                              minNumLaps = num_laps,
                              multiplayer = [0,1])()
        if not res is None:
            totalPages=(res['numberOfSessions']+nip-1)//nip
            r = sesStatTableTemplate.render(sesStatRes=res['sessions'],
                                            tracks=tracks, currtrack=currtrack,
                                            datespan=[from_time[1],to_time[1]],
                                            session_types=session_types,
                                            num_players=num_players,
                                            num_laps=num_laps,
                                            features=self.features())
        else:
            totalPages=1
            r = sesStatTableTemplate.render(sesStatRes=[],
                                            tracks=tracks, currtrack=currtrack,
                                            features=self.features())
        return baseTemplate.render(base=r, pagination=(page,totalPages), src="sesstat", rootpage=self.rootpage, features=self.features(), curr_url=curr_url)

    def sessiondetails(self, sessionid = None, playerInSessionId = None, curr_url=None):
        if not sessionid is None:
            sesId = int(sessionid)
            res = db.sessionDetails(__sync=True, sessionid=sesId)()
            csres = db.csGetSeasons(__sync=True)()
            r = sesDetailsTemplate.render(s=res, features=self.features(), events=csres['events'], point_schemata=csres['point_schemata'], session_id=sesId)
            return baseTemplate.render(base=r, pagination=None, src="sesstat", rootpage=self.rootpage, features=self.features(), curr_url=curr_url)
        elif not playerInSessionId is None:
            pisId = int(playerInSessionId)
            res = db.playerInSessionDetails(__sync=True, pisId=pisId)()
            res['sectorCount'] = 0
            for l in res['laps']:
                c = len(list(filter(lambda x: not x is None, l['sectors'])))
                if c > res['sectorCount']:
                    res['sectorCount'] = c
            r = pisDetailsTemplate.render(res=res, features=self.features())
            return baseTemplate.render(base=r, pagination=None, src="sesstat", rootpage=self.rootpage, features=self.features(), curr_url=curr_url)

    def players(self, search_pattern = "", page = 0, orderby = None, curr_url=None):
        page = int(page)
        nip = self.itemsPerPage
        orderby_src ={'0': 'lastseen', '1': 'drivername'}
        orderby = orderby_src.get(orderby, 'lastseen')
        res = db.getPlayers(__sync=True, limit=[page*nip+1, nip], searchPattern = search_pattern, orderby=orderby)()
        #acdebug("page=%d nip=%d count=%d", page, nip, res['count'])
        r = playersTemplate.render(res=res, search_pattern=search_pattern, features=self.features(), caller = "players")
        return baseTemplate.render(base=r, pagination=(page, (res['count']+nip-1)//nip), src="players", rootpage=self.rootpage, features=self.features(), curr_url=curr_url)

    def playerdetails(self, pid, curr_url=None):
        res = db.playerDetails(__sync=True, playerid=pid)()
        if self.isAdmin():
            res['groups'] = db.allgroups(__sync=True)()
        r = plyDetailsTemplate.render(http_server=self, ply=res, features=self.features())
        return baseTemplate.render(base=r, pagination=None, src="players", rootpage=self.rootpage, features=self.features(), curr_url=curr_url)

    def mainpage(self, curr_url=None):
        r = mainPageTemplate.render(features=self.features())
        return baseTemplate.render(base=r, pagination=None, src="main", rootpage=self.rootpage, features=self.features(), curr_url=curr_url)

    @cherrypy.tools.json_out()
    def lapsper_data(self):
        stats = self.lastStat
        per_track_data = list(sorted(stats['lapsPerTrack'].items(), key=lambda x: x[1], reverse=True))
        per_car_data = list(sorted(stats['lapsPerCar'].items(), key=lambda x: x[1], reverse=True))
        per_combo_data = sorted(stats['lapsPerCombo'].values(), key=lambda x: x['lapCount'], reverse=True)
        # There's more than we need, plus the car (can only be 1 for a combo)
        # is inside a list
        per_combo_data = list(map(lambda row: {
            'lapCount': row['lapCount'],
            'car': row['uicars'][0],
            'track': row['uitrack'],
        }, per_combo_data))
        data = {
            'lapsPerTrack': per_track_data,
            'lapsPerCar': per_car_data,
            'lapsPerCombo': per_combo_data,
        }
        
        cherrypy.response.headers['Access-Control-Allow-Origin'] = '*'
        return data

    def statistics(self, servers=None, date_from=None, date_to=None, tracks=None, cars=None, curr_url=None):

        date_from = self.toTimestamp(date_from)
        date_to = self.toTimestamp(date_to,24*60*60) # to should be inclusive

        if not servers is None:
            servers = servers.split(",")

        if not tracks is None:
            tracks = tracks.split(",")

        if not cars is None:
            cars = cars.split(",")

        stats = db.statistics(__sync=True, servers=servers, startDate=date_from[0], endDate=date_to[0], tracks=tracks, cars=cars)()
        allservers = sorted(db.allservers(__sync=True)())
        alltracks = sorted(db.alltracks(__sync=True)(), key=lambda x: x['uitrack'])
        allcars = sorted(db.allcars(__sync=True)(), key=lambda x: x['uicar'])

        self.lastStat = stats
        r = statisticsTemplate.render(stats=stats, currservers=servers, servers=allservers, date_from=date_from, date_to=date_to,
                                      currtracks=tracks, tracks=alltracks, currcars=cars, cars=allcars, http_server=self, features=self.features(), curr_url=curr_url)
        return baseTemplate.render(base=r, pagination=None, src="stats", rootpage=self.rootpage, features=self.features(), curr_url=curr_url)

    @cherrypy.tools.json_out()
    def online_per_day_data(self):
        stats = self.lastStat['numPlayersOnlinePerDay']
        stats = list(map(lambda row: [ row['datetime'].date().isoformat(), row['count']], stats))
        
        cherrypy.response.headers['Access-Control-Allow-Origin'] = '*'
        return stats

    @cherrypy.tools.json_out()
    def chart_data(self, lapid):
        lapid = int(lapid)
        ci = db.comparisonInfo([lapid],__sync=True)()
        if len(ci) == 0:
            raise cherrypy.HTTPError(404)
        length = ci[lapid]['length']
        track_id = ci[lapid]['track']
        st, wp, vel, nsp = decompress(ci[lapid]['historyinfo'])
        # Every item in vel is velocities in m/s for 3 axes, convert
        # to a single velocity in km/h, rounded to 1 decimal
        v = map(lambda x: round(3.6 * math.sqrt(x[0]**2+x[1]**2+x[2]**2), 1), vel)
        if length is not None:
            # Not sure why the min/max is being done here. Obviously
            # to clamp the distance between 0 and end of track, but
            # unsure when that would happen...
            # nsp = list(map(lambda x: min(l, max(0, x*l)), nsp))
            # Normalized Spline Position is a float in range 0.0 to 1.0
            # convert to meters.
            nsp = list(map(lambda x: round(x * length, 1), nsp))
        output = {
            'lap_id': lapid,
            'track': {
                'id': track_id,
                'name': ci[lapid]['uitrack'],
                'length': length,
            },
            'car': ci[lapid]['uicar'],
            'player': ci[lapid]['player'],
            'laptime': format_time(ci[lapid]['laptime'], False),
            'velocities': list(zip(nsp, v)),
        }
        td = self.trackAndCarDetails()['tracks']
        td = dict(map(lambda x: (x['acname'], x), td))
        self.trackmap(track=track_id, curr_url=None)
        if track_id in td and td[track_id]['mapdata']:
            mapdata = pickle.loads(td[track_id]['mapdata'])
            scale = 1./float(mapdata['ini']['scale'])
            width = float(mapdata['ini']['width'])
            height = float(mapdata['ini']['height'])
            offsetx = float(mapdata['ini']['xoffset'])
            offsetz = float(mapdata['ini']['zoffset'])
            # looks like Y-axis in AC is height, so we use Z-axis in AC
            # as Y-axis in our map. This is in meters, so rounding to 
            # 1 decimal is more than enough
            x = [max(0, min(width, round((pos[0] + offsetx) * scale, 1))) for pos in wp]
            y = [max(0, min(height, round((pos[2] + offsetz) * scale, 1))) for pos in wp]
            output['positions'] = list(zip(x, y))

        cherrypy.response.headers['Access-Control-Allow-Origin'] = '*'
        return output

    @cherrypy.tools.json_out()
    def track_data(self, track_id):
        td = self.trackAndCarDetails()['tracks']
        td = dict(map(lambda x: (x['acname'], x), td))
        self.trackmap(track=track_id, curr_url=None)
        output = {'id': track_id}
        sections = []
        if track_id in td:
            if td[track_id]['mapdata']:
                mapdata = pickle.loads(td[track_id]['mapdata'])
                output['map'] = {
                    'width': float(mapdata['ini']['width']),
                    'height': float(mapdata['ini']['height']),
                }
                if 'sections' in mapdata:
                    length = td[track_id]['length']
                    for section in mapdata['sections']:
                        sections.append({
                            'text': section['text'],
                            'in': round(section['in'] * length),
                            'out': round(section['out'] * length),
                        })
                output['sections'] = sections
        else:
            raise cherrypy.HTTPError(404)
        cherrypy.response.headers['Access-Control-Allow-Origin'] = '*'
        return output

    def championship(self, cs_id=None, event_id=None, event_session_id=None, point_schema_id=None, team_score=0, curr_url=None):
        if not cs_id is None: cs_id = int(cs_id)
        if not event_id is None: event_id = int(event_id)
        if cs_id is None:
            csResTmp = db.csGetSeasons(__sync=True)()
            if len(csResTmp['seasons']) > 0:
                if event_id is None:
                    cs_id = csResTmp['seasons'][0]['id']
                else:
                    for e in csResTmp['events']:
                        if e['id'] == event_id:
                            cs_id = e['cs_id']
                            break
        csRes = db.csGetSeasons(__sync=True, cs_id=cs_id)()
        r = championshipTemplate.render(seasons=csRes['seasons'],
                                        events=csRes['events'],
                                        players=csRes['players'],
                                        teams=csRes['teams'],
                                        cs_id=cs_id,
                                        event_id=event_id,
                                        features=self.features(),
                                        team_score=team_score)
        return baseTemplate.render(base=r, pagination=None, src="cs", rootpage=self.rootpage, features=self.features(), curr_url=curr_url)

    def carbadge(self, car, curr_url=None):
        with self.trackAndCarLock:
            res = self.trackAndCarDetails()
            res = dict(map(lambda x: (x['acname'], x), res['cars']))
            c = res.get(car, None)
            if not c is None:
                b = c.get('badge', None)
                if not b is None:
                    if type(b) != bytes:
                        acdebug("querying badge of %s", car)
                        b = db.carBadge(__sync=True, car=car)()
                        c['badge'] = b
                    return b
            if '://local/' in curr_url:
                # if we are local, the file might be there in the AC directory
                fn = os.path.join("content", "cars", car, "ui", "badge.png")
                try:
                    acdebug("Trying to open local carbadge (%s).", fn)
                    return open(fn, 'rb').read()
                except:
                    pass
            return ""

    def trackmap(self, track, curr_url=None):
        with self.trackAndCarLock:
            res = self.trackAndCarDetails()
            res = dict(map(lambda x: (x['acname'], x), res['tracks']))
            t = res.get(track, None)
            if not t is None:
                md = t.get('mapdata', None)
                if not md is None:
                    if type(md) != bytes:
                        acdebug("querying map of %s", track)
                        md = db.trackMap(__sync=True, track=track)()
                        t['mapdata'] = md
                    return pickle.loads(md)['png']
            if not curr_url is None and '://local' in curr_url:
                fns = [
                    os.path.join("content", "cars", track, "ui", "badge.png"),
                    os.path.join(*["content", "cars"] + track.split('-') + ["map.png"])]
                for fn in fns:
                    try:
                        acdebug("Trying to open local trackmap (%s).", fn)
                        return open(fn, 'rb').read()
                    except:
                        pass
            return ""

    def serve_pts(self, url):
        item = '?'
        query = {}
        try:
            o = urlparse(url)
            item = o.path
            if item[0] == '/':
                item = item[1:]
            query = dict(parse_qsl(o.query))
            headers = {'png': 'application/octet-stream', '':'image/x-png', 'css': 'text/css', '.js': 'application/javascript', 'ttf': 'application/octet-stream'}
            if not item[-3:] in headers:
                item = item.replace('.', '_')
                content = getattr(self, item)(curr_url = url, **query)
                if type(content) == str:
                    content = content.encode('utf-8')
                    ctype = "text/html; charset=utf-8"
                elif type(content) == bytes:
                    ctype = "application/octet-stream"
                else:
                    try:
                        content = bytes(content)
                        ctype = "application/octet-stream"
                    except:
                        content = str(content).encode('utf-8')
                        ctype = "text/html; charset=utf-8"
                acinfo("serving %s(%s) (size=%d)", item, query, len(content))
                return (content, ctype, False)
            else:
                content = None
                for d in ['http_static', 'http_static/bootstrap', 'http_static/img', 'http_static/jquery']:
                    p = os.path.join(self.static_base_dir, d, item)
                    if os.path.exists(p):
                        header = headers[p[-3:]]
                        content = open(p, 'rb').read()
                        acinfo('serving %s size=%d contenttype=%s', p, len(content), header)
                        return (content, header, True)
                if content is None:
                    content = "NOT FOUND"
                    acinfo('serving %s(%s) - not found, base dir = %s', item, query, self.static_base_dir)
                    return (content.encode(), "x-error/not-found", False)
        except:
            content = traceback.format_exc()
            acinfo("serving %s(%s) - error: %s", item, query, content)
            return (content.encode(), "x-error/traceback", False)
