/**
 * Oil Price Tracker - Chart Utilities
 */

// Chart.js default configuration
Chart.defaults.color = '#a0a0a0';
Chart.defaults.borderColor = '#2a2a2a';
Chart.defaults.font.family = "'Inter', sans-serif";

const chartColors = {
    primary: '#5e6ad2',
    success: '#4ade80',
    warning: '#fbbf24',
    error: '#ef4444',
    info: '#38bdf8',
    purple: '#a855f7',
    pink: '#ec4899',
};

const chartConfig = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            position: 'bottom',
            labels: {
                padding: 20,
                usePointStyle: true,
                pointStyle: 'circle',
            },
        },
        tooltip: {
            backgroundColor: '#1f1f1f',
            titleColor: '#f5f5f5',
            bodyColor: '#a0a0a0',
            borderColor: '#2a2a2a',
            borderWidth: 1,
            padding: 12,
            cornerRadius: 8,
            displayColors: true,
            boxPadding: 6,
        },
    },
};

/**
 * Create a price trend line chart
 */
function createPriceTrendChart(ctx, data) {
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: 'Average Price',
                    data: data.datasets.avg,
                    borderColor: chartColors.primary,
                    backgroundColor: 'rgba(94, 106, 210, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 6,
                },
                {
                    label: 'Min Price',
                    data: data.datasets.min,
                    borderColor: chartColors.success,
                    backgroundColor: 'transparent',
                    borderDash: [5, 5],
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 6,
                },
                {
                    label: 'Max Price',
                    data: data.datasets.max,
                    borderColor: chartColors.error,
                    backgroundColor: 'transparent',
                    borderDash: [5, 5],
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 6,
                },
            ],
        },
        options: {
            ...chartConfig,
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'day',
                        displayFormats: {
                            day: 'MMM d',
                        },
                    },
                    grid: {
                        display: false,
                    },
                },
                y: {
                    beginAtZero: false,
                    grid: {
                        color: '#2a2a2a',
                    },
                    ticks: {
                        callback: (value) => `$${value.toFixed(2)}`,
                    },
                },
            },
            plugins: {
                ...chartConfig.plugins,
                tooltip: {
                    ...chartConfig.plugins.tooltip,
                    callbacks: {
                        label: (context) => `${context.dataset.label}: $${context.parsed.y.toFixed(3)}`,
                    },
                },
            },
        },
    });
}

/**
 * Create an order history bar chart
 */
function createOrderChart(ctx, data) {
    const orders = data.orders || [];

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: orders.map(o => o.date),
            datasets: [
                {
                    label: 'Total Cost',
                    data: orders.map(o => o.total_cost),
                    backgroundColor: chartColors.primary,
                    borderRadius: 4,
                    yAxisID: 'y',
                },
                {
                    label: 'Gallons',
                    data: orders.map(o => o.gallons),
                    backgroundColor: chartColors.success,
                    borderRadius: 4,
                    yAxisID: 'y1',
                },
            ],
        },
        options: {
            ...chartConfig,
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'month',
                        displayFormats: {
                            month: 'MMM yyyy',
                        },
                    },
                    grid: {
                        display: false,
                    },
                },
                y: {
                    type: 'linear',
                    position: 'left',
                    grid: {
                        color: '#2a2a2a',
                    },
                    ticks: {
                        callback: (value) => `$${value.toFixed(0)}`,
                    },
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    grid: {
                        drawOnChartArea: false,
                    },
                    ticks: {
                        callback: (value) => `${value} gal`,
                    },
                },
            },
        },
    });
}

/**
 * Create a temperature and usage correlation chart
 */
function createTemperatureChart(ctx, data) {
    const temps = data.temperatures || { labels: [], avg: [] };
    const orders = data.orders || [];

    // Calculate Heating Degree Days (HDD)
    // Base 65°F. HDD = max(0, 65 - avg_temp)
    const hddData = temps.avg.map(t => Math.max(0, 65 - t));

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: temps.labels,
            datasets: [
                {
                    label: 'Heating Demand (HDD)',
                    data: hddData,
                    borderColor: '#f59e0b', // Amber color for Heat Demand
                    backgroundColor: 'rgba(245, 158, 11, 0.2)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    yAxisID: 'y',
                    order: 2
                },
                {
                    label: 'Oil Usage (Gal)',
                    data: orders.map(o => ({ x: o.date, y: o.gallons })),
                    type: 'bar',
                    backgroundColor: 'rgba(59, 130, 246, 0.5)', // Primary Blue with opacity
                    borderColor: 'rgba(59, 130, 246, 1)',
                    borderWidth: 1,
                    barPercentage: 0.8,
                    categoryPercentage: 0.9,
                    yAxisID: 'y1',
                    order: 1
                },
            ],
        },
        options: {
            ...chartConfig,
            interaction: {
                mode: 'index',
                axis: 'x',
                intersect: false,
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'month',
                        displayFormats: {
                            month: 'MMM yyyy'
                        },
                    },
                    grid: {
                        display: false,
                    },
                },
                y: {
                    type: 'linear',
                    position: 'left',
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Heating Degree Days (HDD)',
                        color: '#f59e0b',
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)',
                    },
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Gallons Used',
                        color: chartColors.primary,
                    },
                    grid: {
                        drawOnChartArea: false,
                    },
                },
            },
            plugins: {
                ...chartConfig.plugins,
                tooltip: {
                    ...chartConfig.plugins.tooltip,
                    callbacks: {
                        label: (context) => {
                            if (context.dataset.label.includes('HDD')) {
                                const temp = temps.avg[context.dataIndex];
                                return [
                                    `HDD: ${context.parsed.y.toFixed(1)}`,
                                    `Avg Temp: ${temp ? temp.toFixed(1) + '°F' : 'N/A'}`
                                ];
                            }
                            if (context.dataset.label.includes('Usage')) {
                                return `Usage: ${context.parsed.y.toFixed(1)} gal`;
                            }
                            return `${context.dataset.label}: ${context.parsed.y}`;
                        }
                    }
                },
                legend: {
                    display: true,
                    labels: {
                        usePointStyle: true,
                        color: '#a0a0a0'
                    }
                }
            }
        },
    });
}

/**
 * Create a price comparison chart for latest prices
 */
function createPriceComparisonChart(ctx, prices) {
    const sorted = [...prices].sort((a, b) => a.price_per_gallon - b.price_per_gallon);

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sorted.map(p => p.company_name),
            datasets: [
                {
                    label: 'Price per Gallon',
                    data: sorted.map(p => p.price_per_gallon),
                    backgroundColor: sorted.map((_, i) =>
                        i === 0 ? chartColors.success : chartColors.primary
                    ),
                    borderRadius: 4,
                },
            ],
        },
        options: {
            ...chartConfig,
            indexAxis: 'y',
            scales: {
                x: {
                    grid: {
                        color: '#2a2a2a',
                    },
                    ticks: {
                        callback: (value) => `$${value.toFixed(2)}`,
                    },
                },
                y: {
                    grid: {
                        display: false,
                    },
                },
            },
            plugins: {
                ...chartConfig.plugins,
                legend: {
                    display: false,
                },
                tooltip: {
                    ...chartConfig.plugins.tooltip,
                    callbacks: {
                        label: (context) => `$${context.parsed.x.toFixed(3)}/gal`,
                    },
                },
            },
        },
    });
}

/**
 * Create an order volume and spend insight chart
 */
function createOrderVolumeInsightChart(ctx, orders) {
    const sortedOrders = [...orders].sort((a, b) => new Date(a.start_date) - new Date(b.start_date));

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sortedOrders.map(o => o.start_date),
            datasets: [
                {
                    label: 'Total Spend ($)',
                    data: sortedOrders.map(o => o.total_cost),
                    backgroundColor: chartColors.primary,
                    borderColor: 'transparent',
                    borderRadius: 6,
                    yAxisID: 'y-spend',
                    order: 2,
                },
                {
                    label: 'Volume (Gallons)',
                    data: sortedOrders.map(o => o.gallons),
                    type: 'line',
                    borderColor: chartColors.success,
                    backgroundColor: 'transparent',
                    borderWidth: 3,
                    pointBackgroundColor: chartColors.success,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    tension: 0.3,
                    yAxisID: 'y-volume',
                    order: 1,
                },
            ],
        },
        options: {
            ...chartConfig,
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'month',
                        displayFormats: {
                            month: 'MMM yyyy',
                        },
                    },
                    grid: {
                        display: false,
                    },
                },
                'y-spend': {
                    type: 'linear',
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Total Spend ($)',
                    },
                    grid: {
                        color: '#2a2a2a',
                    },
                    ticks: {
                        callback: (value) => `$${value.toFixed(0)}`,
                    },
                },
                'y-volume': {
                    type: 'linear',
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Volume (Gallons)',
                    },
                    grid: {
                        drawOnChartArea: false,
                    },
                    ticks: {
                        callback: (value) => `${value} gal`,
                    },
                },
            },
            plugins: {
                ...chartConfig.plugins,
                tooltip: {
                    ...chartConfig.plugins.tooltip,
                    callbacks: {
                        label: (context) => {
                            if (context.dataset.label.includes('Spend')) {
                                return `Spend: $${parseFloat(context.parsed.y).toFixed(2)}`;
                            }
                            return `Volume: ${parseFloat(context.parsed.y).toFixed(1)} gal`;
                        }
                    }
                }
            }
        },
    });
}

/**
 * Create a Yearly Order Insight chart showing tons of data
 */
function createYearlyOrderInsightChart(ctx, data) {
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.year),
            datasets: [
                {
                    label: 'Total Cost ($)',
                    data: data.map(d => d.total_cost),
                    backgroundColor: chartColors.primary + '80',
                    borderColor: chartColors.primary,
                    borderWidth: 1,
                    yAxisID: 'y',
                    order: 2
                },
                {
                    label: 'Gallons',
                    data: data.map(d => d.total_gallons),
                    backgroundColor: chartColors.success + '40',
                    borderColor: chartColors.success,
                    borderWidth: 1,
                    yAxisID: 'y1',
                    order: 3
                },
                {
                    label: 'Avg Price ($/gal)',
                    data: data.map(d => d.avg_price_per_gallon),
                    type: 'line',
                    borderColor: chartColors.warning,
                    backgroundColor: 'transparent',
                    borderWidth: 3,
                    pointRadius: 4,
                    tension: 0.3,
                    yAxisID: 'y2',
                    order: 1
                }
            ]
        },
        options: {
            ...chartConfig,
            scales: {
                x: {
                    grid: { display: false }
                },
                y: {
                    type: 'linear',
                    position: 'left',
                    title: { display: true, text: 'Cost / Gallons' },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    display: false, // Hidden but used for scaling if needed, or we can just use y
                },
                y2: {
                    type: 'linear',
                    position: 'right',
                    title: { display: true, text: 'Avg Price ($/gal)' },
                    grid: { drawOnChartArea: false },
                    ticks: {
                        callback: (val) => `$${val.toFixed(2)}`
                    }
                }
            },
            plugins: {
                ...chartConfig.plugins,
                tooltip: {
                    ...chartConfig.plugins.tooltip,
                    callbacks: {
                        label: (context) => {
                            const val = context.parsed.y;
                            if (context.dataset.label.includes('Cost')) return `Cost: $${val.toLocaleString()}`;
                            if (context.dataset.label.includes('Avg')) return `Avg Price: $${val.toFixed(3)}/gal`;
                            return `Gallons: ${val.toLocaleString()} gal`;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Create a Year-over-Year comparison chart
 */
function createYoYComparisonChart(ctx, data, metricLabel) {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    // Expert UX: If viewing gallons/cost, also show HDD to see correlation
    const showHDD = metricLabel === 'usage_gallons' || metricLabel === 'usage_cost';
    const hddData = data.current.map(m => m.total_hdd);

    const datasets = [
        {
            label: `${data.current_year} (Current)`,
            data: data.current.map(m => m[metricLabel]),
            backgroundColor: chartColors.primary,
            borderRadius: 4,
            order: 2,
            yAxisID: 'y'
        },
        {
            label: `${data.previous_year} (Previous)`,
            data: data.previous.map(m => m[metricLabel]),
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
            borderRadius: 4,
            order: 3,
            yAxisID: 'y'
        }
    ];

    if (showHDD) {
        datasets.push({
            label: `Heating Demand (HDD)`,
            data: hddData,
            type: 'line',
            borderColor: '#f59e0b',
            borderWidth: 2,
            pointRadius: 3,
            tension: 0.4,
            fill: false,
            order: 1,
            yAxisID: 'y1'
        });
    }

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: months,
            datasets: datasets
        },
        options: {
            ...chartConfig,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                x: {
                    grid: { display: false }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: {
                        callback: (value) => (metricLabel.includes('cost') || metricLabel.includes('price')) ? `$${value.toFixed(2)}` : value
                    }
                },
                y1: {
                    type: 'linear',
                    display: showHDD,
                    position: 'right',
                    beginAtZero: true,
                    title: { display: true, text: 'HDD (Heating Demand)' },
                    grid: { drawOnChartArea: false },
                    ticks: { color: '#f59e0b' }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    align: 'end',
                    labels: { boxWidth: 12, usePointStyle: true }
                }
            }
        }
    });
}

/**
 * Create a mini sparkline chart for table rows
 */
function createSparkline(ctx, data) {
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.date),
            datasets: [{
                data: data.map(d => d.price),
                borderColor: chartColors.primary,
                borderWidth: 2,
                pointRadius: 0,
                fill: false,
                tension: 0.4
            }]
        },
        options: {
            maintainAspectRatio: false,
            responsive: true,
            layout: { padding: 2 },
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            scales: {
                x: { display: false },
                y: { display: false }
            },
            events: []
        }
    });
}

// Store chart instances for cleanup
const chartInstances = {};

function destroyChart(id) {
    if (chartInstances[id]) {
        chartInstances[id].destroy();
        delete chartInstances[id];
    }
}

function storeChart(id, chart) {
    destroyChart(id);
    chartInstances[id] = chart;
}

function resizeAllCharts() {
    Object.values(chartInstances).forEach(chart => {
        if (chart && typeof chart.resize === 'function') {
            chart.resize();
        }
    });
}
