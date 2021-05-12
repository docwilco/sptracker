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
                text: '% laps driven'
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
                    const total = group.value;
                    const percentage = point.value / total;
                    const val = (percentage === undefined) ? point.value : (percentage * 100).toFixed(1) + '%';
                    // cars and tracks need parent & own names flipped from eachother
                    // and only the outer rim needs both
                    if (group.id == 'cars' && point.parent != 'cars') {
                        return parent_name + ' @ ' + point.name + '<br>' + val;
                    } else if (group.id == 'tracks' && point.parent != 'tracks') {
                        return point.name + ' @ ' + parent_name + '<br>' + val;
                    } else {
                        return point.name + '<br>' + val;
                    }
                },
            },

        });
    });