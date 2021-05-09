const zip = (a, b) => a.map((k, i) => [k, b[i]]);

let lapIDs = velocityOverDistanceParameters['lapIDs'];
let labels = velocityOverDistanceParameters['labels'];
if (labels !== null) {
    // fromEntries will cause lapID deduplication,
    // last label for a lapID wins. 
    labels = Object.fromEntries(zip(lapIDs, labels));
} else {
    labels = {};
}
// now dedup the lapIDs
lapIDs = Array.from(new Set(lapIDs));

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
});

function addSections(trackData) {
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
    chart.xAxis[0].update({ plotBands: plotBands });
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
            lap.prefix = lap.lap_id in labels ? labels[lap.lap_id].concat(':') : "";
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
            .then(trackData => addSections(trackData));
    } else {
        title = "Lap Comparison (warning: different tracks!)";
    }
    let series = [];
    lapData.forEach(lap => {
        let suffix = carsame ? "" : lap.car;
        let label = `${lap.prefix}${lap.laptime} by ${lap.player}${suffix}`;
        series.push({ name: label, data: lap.velocities });
    })
    chart.update({
        title: { text: title },
        series: series
    }, true, true);

}

const lapFetches = lapIDs.map(lapID =>
    fetch(`chart_data?lapid=${lapID}`)
    .then(response => response.json())
);
Promise.allSettled(lapFetches).then(results => drawCharts(results));