// The chart syncing stuff is gleaned from:
// https://jsfiddle.net/gh/get/library/pure/highcharts/highcharts/tree/master/samples/highcharts/demo/synchronized-charts

const zip = (a, b) => a.map((k, i) => [k, b[i]]);

/**
 * In order to synchronize tooltips and crosshairs, override the
 * built-in events with handlers defined on the parent element.
 */
['mousemove', 'touchmove', 'touchstart'].forEach(eventType => {
    ['velocity-over-distance', 'track-map'].forEach(container => {
        document.getElementById(container).addEventListener(
            eventType,
            function(e) {
                var chart,
                    point,
                    i,
                    event;
                const charts = [];
                for (i = 0; i < Highcharts.charts.length; i = i + 1) {
                    chart = Highcharts.charts[i];
                    charts[chart.renderTo.id] = chart;
                }
                chart = charts[container];
                // Find coordinates within the chart
                event = chart.pointer.normalize(e);
                // Get the hovered point
                let series;
                if (container == 'track-map') {
                    series = chart.series.filter(series => series.options.enableMouseTracking);
                } else {
                    series = chart.series.filter(series => series.visible);
                }
                point = chart.pointer.findNearestKDPoint(series, false, event);
                if (point) {
                    point.highlight(e);
                    let otherChart;
                    if (container == 'track-map') {
                        otherChart = charts['velocity-over-distance'];
                    } else {
                        otherChart = charts['track-map'];
                    }
                    let otherSeries = otherChart.series[point.series.index];
                    if (otherSeries) {
                        let otherPoint = otherSeries.points[point.index];
                        if (otherPoint) {
                            otherPoint.highlight(e);
                        }
                    }
                }
            }
        );
    })
});

// This is needed to keep the tooltip on the other charts around.
// Just happens to also stop the bug where resetting the zoom starts
// a new zoom drag action (for 2 or more series, race condition?).
Highcharts.Pointer.prototype.reset = function() {
    return undefined;
};

Highcharts.Point.prototype.highlight = function(event) {
    event = this.series.chart.pointer.normalize(event);
    this.onMouseOver(); // Show the hover marker
    this.series.chart.tooltip.refresh(this); // Show the tooltip
};

let lapIDs = velocityOverDistanceParameters.lapIDs;
let labels = velocityOverDistanceParameters.labels;
if (labels !== null) {
    // fromEntries will cause lapID deduplication,
    // last label for a lapID wins. 
    labels = Object.fromEntries(zip(lapIDs, labels));
} else {
    labels = {};
}
// now dedup the lapIDs
lapIDs = Array.from(new Set(lapIDs));
let trackData = null;
let trackImage = null;

function drawTrackImage() {
    if (trackData === null) {
        return;
    }
    // left/right/top/bottom x/y
    lx = trackMap.xAxis[0].toPixels(0);
    rx = trackMap.xAxis[0].toPixels(trackData.map.width);
    ty = trackMap.yAxis[0].toPixels(0);
    by = trackMap.yAxis[0].toPixels(trackData.map.height);
    if (trackImage !== null) {
        let oldTrackImage = trackImage;
        setTimeout(() => oldTrackImage.destroy());
    }
    trackImage = trackMap.renderer.image(`trackmap?track=${trackData.id}`,
        lx,
        ty,
        rx - lx,
        by - ty
    );
    trackImage.clip(trackMap.renderer.clipRect(trackMap.plotLeft, trackMap.plotTop, trackMap.plotWidth, trackMap.plotHeight));
    trackImage.add();
}

const chart = Highcharts.chart('velocity-over-distance', {
    chart: {
        type: 'spline',
        zoomType: "xy"
    },
    title: {
        text: 'Lap Comparison'
    },
    xAxis: {
        title: {
            text: 'Track Position [m]'
        }
    },
    yAxis: {
        title: {
            text: 'Velocity [km/h]'
        }
    },
    plotOptions: {
        series: {
            events: {
                hide: function(e) {
                    trackMap.series[this.index].update({ enableMouseTracking: false });
                    trackMap.series[this.index + this.chart.series.length].hide();
                },
                show: function(e) {
                    trackMap.series[this.index].update({ enableMouseTracking: true });
                    trackMap.series[this.index + this.chart.series.length].show();
                },
            },
        }
    },
    tooltip: {
        headerFormat: '@{point.x} m<br>',
        valueSuffix: ' km/h',
    }
});

const trackMap = Highcharts.mapChart('track-map', {
    chart: {
        events: {
            redraw: drawTrackImage
        },

    },
    title: {
        // Setting to null is the only way to remove the title
        text: null,
    },
    legend: {
        enabled: false,
    },
    mapNavigation: {
        enabled: true,
        // mouse wheel zoom doesn't seem to work, but does capture
        // the mouse wheel, preventing people from scrolling the page.
        enableMouseWheelZoom: false,
    },
    plotOptions: {
        mappoint: {
            marker: {
                enabled: false,
            }
        },
        mapline: {
            enableMouseTracking: false,
            lineWidth: 2,
        }
    },
    tooltip: {
        pointFormatter: function(tooltip) {
            try {
                let speed = chart.series[this.series.index].points[this.index].y;
                return `${speed} km/h`;
            } catch (e) {}
        }
    },
    xAxis: {
        // Allow for decently close zoom
        minRange: 100,
    },
    yAxis: {
        minRange: 100,
    },

});

function addTrackData(data) {
    trackData = data;
    plotBands = [];
    trackData.sections.forEach(section => {
        plotBands.push({
            from: section.in,
            to: section.out,
            color: '#eeeeee',
            label: {
                text: section.text,
                rotation: 90,
                textAlign: 'left'
            }
        })
    })
    chart.xAxis[0].update({
        plotBands: plotBands
    });
    // make sure the entire map is shown
    trackMap.addSeries({
        type: 'mappoint',
        name: 'extremes',
        enableMouseTracking: false,
        data: [{
            x: 0,
            y: 0
        }, {
            x: trackData.map.width,
            y: trackData.map.height
        }]
    });
}

function drawCharts(results) {
    let car = null;
    let trackId = null;
    let trackName = null;
    let carsame = true;
    let tracksame = true;
    let title;
    const lapData = [];
    results.forEach(result => {
        if (result.status == "fulfilled") {
            lap = result.value;
            lapData.push(lap);
        }
    });
    lapData.forEach(lap => {
        if (car === null) {
            car = lap.car;
        } else {
            if (car != lap.car) {
                carsame = false;
            }
        }
        if (trackId === null) {
            trackId = lap.track.id;
            trackName = lap.track.name;
        } else {
            if (trackId != lap.track.id) {
                tracksame = false;
            }
        }
    });
    if (tracksame) {
        if (carsame) {
            title = `Lap Comparison ${car} @ ${trackName}`;
        } else {
            title = `Lap Comparison on ${trackName}`;
        }
        fetch(`track_data?track_id=${trackId}`)
            .then(response => response.json())
            .then(trackData => addTrackData(trackData));
    } else {
        title = "Lap Comparison (warning: different tracks!)";
    }
    let series = [];
    let mapPointSeries = [];
    let mapLineSeries = [];
    lapData.forEach((lap, index) => {
        let suffix = carsame ? "" : lap.car;
        let lap_type = lap.lap_id in labels ? labels[lap.lap_id] : "";
        let prefix = lap_type == "" ? "" : lap_type + ": ";
        let label = `${prefix}${lap.laptime} by ${lap.player}${suffix}`;
        // By default only show the Current lap and the overall
        // server Best. The current lap _could_ be Personal Best,
        // Session Best, or Personal Session Best.
        const visible = lap_type == 'Server Best' || lap.lap_id == lapIDs[0];
        series.push({
            name: label,
            data: lap.velocities,
            visible: visible,
        });
        let positions = [];
        // SVG lines start with M x y (move to x,y), and then have L x y (line to x,y)
        // for each segment. So we prime with an M, then add x y L for each point,
        // and strip the final L.
        let path = ['M'];
        lap.positions.forEach(pos => {
            positions.push({ x: pos[0], y: pos[1] });
            path.push(pos[0]);
            path.push(pos[1]);
            path.push('L');
        });
        // strip final L 
        path.pop();
        mapPointSeries.push({
            type: 'mappoint',
            name: label,
            data: positions,
            enableMouseTracking: visible,
        });
        mapLineSeries.push({
            type: 'mapline',
            name: label,
            color: chart.options.colors[index],
            data: [{
                path: path
            }],
            visible: visible,
        })
    });
    lapData.forEach(lap => {});
    chart.update({
        title: {
            text: title
        },
        series: series
    }, true, true);

    let mapSeries = mapPointSeries.concat(mapLineSeries);
    trackMap.update({
        series: mapSeries
    }, true, true);
}

const lapFetches = lapIDs.map(lapID =>
    fetch(`chart_data?lapid=${lapID}`)
    .then(response => response.json())
);
Promise.allSettled(lapFetches).then(results => drawCharts(results));