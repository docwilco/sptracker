fetch('https://stracker.drwil.co/online_per_day_data')
    .then(response => response.json())
    .then(json => {
        Highcharts.chart('server-usage', {
            chart: {
                type: 'area'
            },
            title: {
                text: 'Server usage'
            },

            legend: {
                enabled: false
            },

            yAxis: {
                title: null
            },
            data: {
                firstRowAsNames: false,
                rows: json,
            },
            plotOptions: {
                series: {
                    marker: {
                        enabled: false
                    }
                }
            },
            series: [{
                name: "Drivers online",
            }],
        });
    });