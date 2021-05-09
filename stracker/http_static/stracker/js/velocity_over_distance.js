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

function drawCharts(results) {
    let car = null;
    let track = null;
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
            car = lap['car'];
        } else {
            if (car != lap['car']) {
                carsame = false;
            }
        }
        if (track === null) {
            track = lap['track']['name'];
        } else {
            if (track != lap['track']['name']) {
                tracksame = false;
            }
        }
    });
    if (tracksame && carsame) {
        title = `Lap Comparison ${car} @ ${track}`;
    } else if (tracksame) {
        title = `Lap Comparison on {@track}`;
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
    //fetch(`https://stracker.drwil.co/chart_data?lapid=${lapID}`)
    fetch(`chart_data?lapid=${lapID}`)
    .then(response => response.json())
);
Promise.allSettled(lapFetches).then(results => drawCharts(results));