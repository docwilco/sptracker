var data = [{
    id: 'root',
    parent: '',
    name: ' ',
}, {
    id: 'cars',
    parent: 'root',
    name: 'Cars',
}, {
    id: 'tracks',
    parent: 'root',
    name: 'Tracks',
}];

fetch('lapsper_data')
    .then(response => response.json())
    .then(json => {
        for (const [car, laps] of json.lapsPerCar) {
            data.push({
                id: car,
                parent: 'cars',
                name: car,
                value: laps,
            })
        }
        for (const [track, laps] of json.lapsPerTrack) {
            data.push({
                id: track,
                parent: 'tracks',
                name: track,
                value: laps,
            })
        }
        json.lapsPerCombo.forEach(combo => {
            data.push({
                parent: combo.track,
                name: combo.car,
                value: combo.lapCount,
            });
            data.push({
                parent: combo.car,
                name: combo.track,
                value: combo.lapCount,
            });
        });
        // transparent for the center circle, use local
        // copy to prevent fucking up other graphs
        colors = ['transparent'].concat(Highcharts.getOptions().colors);

        Highcharts.chart('track-car-usage', {
            colors: colors,
            chart: {
                height: '75%'
            },
            title: {
                text: 'Track and Car usage'
            },
            subtitle: {
                text: 'Click to drill down'
            },
            series: [{
                type: 'sunburst',
                data: data,
                dataSorting: {
                    enabled: true
                },
                allowDrillToNode: true,
                cursor: 'pointer',
                levels: [{
                        level: 1,
                        levelIsConstant: false,
                    }, {
                        level: 2,
                        colorByPoint: true
                    },
                    {
                        level: 3,
                        colorVariation: {
                            key: 'brightness',
                            to: -0.5
                        }
                    }, {
                        level: 4,
                        colorVariation: {
                            key: 'brightness',
                            to: 0.5
                        }
                    }
                ],
            }],
            plotOptions: {
                sunburst: {
                    startAngle: -90,
                },
            },
            tooltip: {
                formatter: function() {
                    const point = this.point,
                        series = this.series;

                    if (point.parent == '') {
                        return false;
                    }
                    if (point.parent == 'root') {
                        return `Click to toggle showing just ${point.name}`;
                    }

                    // For total just step up parents until hitting `cars` or `tracks`
                    let group = series.chart.get(point.parent);
                    const parent_name = group.name;
                    while (group.id != 'tracks' && group.id != 'cars') {
                        group = series.chart.get(group.parent);
                    }
                    // To avoid confusion
                    const top_level = group;
                    const total = top_level.value;
                    const percentage = point.value / total;
                    const val = (percentage === undefined) ? point.value : (percentage * 100).toFixed(1) + '% of total laps driven';
                    // cars and tracks need parent & own names flipped from eachother
                    // and only the outer ring needs both
                    // for the outer ring, the top level group id is not the parent
                    let label;
                    if (point.parent != top_level.id) {
                        let car, track;
                        if (top_level.id == 'cars') {
                            car = parent_name;
                            track = point.name;
                        } else {
                            car = point.name;
                            track = parent_name;
                        }
                        label = point.name + ' @ ' + parent_name;
                    } else {
                        // middle ring
                        label = point.name;
                    }
                    return label + '<br>' + val;
                },
            },

        });
    });