fetch('https://stracker.drwil.co/online_per_day_data')
    .then(response => response.json())
    .then(json => {
        const server_usage = Highcharts.chart('server-usage', {
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
        const extremes = server_usage.xAxis[0].getExtremes();
        let interval = extremes.dataMax - extremes.dataMin;
        console.log(interval);
        interval /= 86400000; // day in milliseconds
        interval += 1;
        server_usage.update({ title: { text: `Server usage over ${interval} days` } })
    });