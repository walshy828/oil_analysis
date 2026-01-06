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
                color: '#a0a0a0'
            },
        },
        tooltip: {
            backgroundColor: 'rgba(20, 20, 22, 0.95)',
            titleColor: '#f5f5f5',
            bodyColor: '#a1a1aa',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            padding: 12,
            cornerRadius: 8,
            displayColors: true,
            boxPadding: 6,
            bodyFont: { family: "'Inter', sans-serif" },
            titleFont: { family: "'Inter', sans-serif", weight: 'bold' }
        },
    },
};

/**
 * Create a price trend line chart
 */
function createPriceTrendChart(ctx, data) {
    const existing = Chart.getChart(ctx);
    if (existing) existing.destroy();
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
    const existing = Chart.getChart(ctx);
    if (existing) existing.destroy();
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
    // Expert UX: Ensure we don't leave zombie charts on the shared canvas
    // This handles race conditions where multiple analytics requests return out of order
    const existingIcon = Chart.getChart(ctx);
    if (existingIcon) {
        existingIcon.destroy();
    }

    const temps = data.temperatures || { labels: [], avg: [] };
    const orders = data.orders || [];

    // Calculate Heating Degree Days (HDD)
    // Base 65°F. HDD = max(0, 65 - avg_temp)
    const hddData = temps.avg.map(t => (t === null || t === undefined) ? null : Math.max(0, 65 - t));

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: temps.labels,
            datasets: [
                {
                    label: 'Heating Demand (HDD)',
                    data: hddData, // Use aligned array data matching labels
                    borderColor: '#f59e0b',
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
                    data: orders.map(o => o.gallons), // Use simple array, assuming orders align with temps/labels
                    type: 'bar',
                    backgroundColor: 'rgba(59, 130, 246, 0.5)',
                    borderColor: 'rgba(59, 130, 246, 1)',
                    borderWidth: 1,
                    barPercentage: 0.6,
                    categoryPercentage: 0.8,
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
    const existing = Chart.getChart(ctx);
    if (existing) existing.destroy();
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
    const existing = Chart.getChart(ctx);
    if (existing) existing.destroy();
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
    const existing = Chart.getChart(ctx);
    if (existing) existing.destroy();
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.year.toString()),
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
                    yAxisID: 'y', // Share primary axis
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
                    tension: 0.2,
                    yAxisID: 'y1', // Use secondary axis (was y2)
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
                    title: { display: true, text: 'Cost & Gallons' },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    title: { display: true, text: 'Avg Price ($/gal)' },
                    grid: { drawOnChartArea: false },
                    ticks: {
                        callback: (val) => {
                            if (val === null || val === undefined) return '';
                            return `$${Number(val).toFixed(2)}`;
                        }
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
function createMultiYearComparisonChart(ctx, combinedData, metricLabel) {
    const existing = Chart.getChart(ctx);
    if (existing) existing.destroy();
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    // Aesthetic color palette for multiple years
    const yearColors = [
        '#5e6ad2', // Primary
        '#8b5cf6', // Violet
        '#ec4899', // Pink
        '#f43f5e', // Rose
        '#f59e0b', // Amber
        '#10b981', // Emerald
        '#06b6d4', // Cyan
    ];

    const datasets = combinedData.datasets.map((ds, i) => {
        const color = yearColors[i % yearColors.length];
        return {
            label: ds.year.toString(),
            data: ds.data.map(m => m[metricLabel]),
            borderColor: color,
            backgroundColor: i === 0 ? `rgba(${hexToRgb(color)}, 0.1)` : 'transparent',
            borderWidth: i === 0 ? 3 : 2, // Highlight the newest year
            fill: i === 0, // Only fill for the primary year to avoid clutter
            tension: 0.4,
            pointRadius: i === 0 ? 4 : 2,
            yAxisID: 'y'
        };
    });

    // Expert UX: Average HDD line across selected years to see "normal" vs "outliers"
    if (combinedData.datasets.length > 0) {
        const avgHdd = months.map((_, mIdx) => {
            const hdds = combinedData.datasets.map(ds => ds.data[mIdx]?.total_hdd || 0);
            return hdds.reduce((a, b) => a + b, 0) / hdds.length;
        });

        datasets.push({
            label: 'Avg Heating Demand (HDD)',
            data: avgHdd,
            type: 'line',
            borderColor: 'rgba(255, 255, 255, 0.2)',
            borderDash: [5, 5],
            borderWidth: 1,
            pointRadius: 0,
            fill: false,
            yAxisID: 'y1',
            order: 99
        });
    }

    return new Chart(ctx, {
        type: 'line', // Line is better for multi-year overlay
        data: {
            labels: months,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#94a3b8', font: { size: 10 } }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    callbacks: {
                        label: (ctx) => {
                            const val = ctx.parsed.y;
                            let label = ctx.dataset.label + ': ';
                            if (ctx.datasetIndex < combinedData.datasets.length) {
                                if (metricLabel.includes('cost') || metricLabel === 'avg_price') {
                                    label += '$' + val.toFixed(2);
                                } else {
                                    label += val.toFixed(1);
                                }
                            } else {
                                label += val.toFixed(0) + ' HDD';
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: metricLabel.replace('_', ' ').toUpperCase(), color: '#94a3b8' },
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8' }
                },
                y1: {
                    position: 'right',
                    beginAtZero: true,
                    title: { display: true, text: 'HDD', color: '#f59e0b' },
                    grid: { display: false },
                    ticks: { color: '#f59e0b' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' }
                }
            }
        }
    });
}

function hexToRgb(hex) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `${r}, ${g}, ${b}`;
}

/**
 * Create a chart comparing multiple companies
 */
function createMultiCompanyTrendChart(ctx, datasets) {
    const existing = Chart.getChart(ctx);
    if (existing) existing.destroy();

    const colors = [
        '#3b82f6', // Blue
        '#10b981', // Emerald
        '#f59e0b', // Amber
        '#ef4444', // Red
        '#8b5cf6', // Violet
        '#ec4899', // Pink
        '#06b6d4'  // Cyan
    ];

    const chartDatasets = datasets.map((ds, i) => {
        const color = colors[i % colors.length];
        return {
            label: ds.name,
            data: ds.history.map(h => ({ x: h.date, y: h.price })),
            borderColor: color,
            backgroundColor: 'transparent',
            borderWidth: 2,
            tension: 0.3,
            pointRadius: 0,
            pointHoverRadius: 4,
            spanGaps: true
        };
    });

    return new Chart(ctx, {
        type: 'line',
        data: {
            datasets: chartDatasets
        },
        options: {
            ...chartConfig,
            interaction: {
                mode: 'index',
                intersect: false
            },
            scales: {
                x: {
                    type: 'time',
                    time: { unit: 'month' },
                    grid: { display: false }
                },
                y: {
                    title: { display: true, text: 'Price ($/gal)', color: '#a0a0a0' },
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: {
                        callback: (val) => `$${val.toFixed(2)}`
                    }
                }
            },
            plugins: {
                ...chartConfig.plugins,
                legend: {
                    display: true,
                    position: 'top',
                    labels: { boxWidth: 12, usePointStyle: true, color: '#a0a0a0' }
                },
                tooltip: {
                    ...chartConfig.plugins.tooltip,
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: $${ctx.parsed.y.toFixed(3)}`
                    }
                }
            }
        }
    });
}

function createYoYComparisonChart(ctx, data, metricLabel) {
    const existing = Chart.getChart(ctx);
    if (existing) existing.destroy();
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
    const prices = data.map(d => d.price);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const spread = maxPrice - minPrice;

    // If the price change is very small (less than 10 cents), 
    // force a minimum range so the line doesn't look like a dramatic trend.
    const hasSmallSpread = spread < 0.1;
    const yMin = hasSmallSpread ? minPrice - (0.1 - spread) / 2 : undefined;
    const yMax = hasSmallSpread ? maxPrice + (0.1 - spread) / 2 : undefined;

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.date),
            datasets: [{
                data: prices,
                borderColor: chartColors.primary,
                borderWidth: 2,
                pointRadius: 0,
                fill: false,
                tension: 0.1 // Straighter lines for sparklines
            }]
        },
        options: {
            maintainAspectRatio: false,
            responsive: true,
            layout: { padding: { top: 5, bottom: 5 } },
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: true,
                    mode: 'index',
                    intersect: false,
                    position: 'nearest',
                    backgroundColor: 'rgba(0, 0, 0, 0.9)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    padding: 4,
                    displayColors: false,
                    titleFont: { size: 10 },
                    bodyFont: { size: 10 },
                    callbacks: {
                        title: (items) => {
                            const d = new Date(items[0].label);
                            return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
                        },
                        label: (item) => `$${item.parsed.y.toFixed(3)}`
                    }
                }
            },
            scales: {
                x: { display: false },
                y: {
                    display: false,
                    min: yMin,
                    max: yMax,
                    padding: 5
                }
            }
        }
    });
}

// Store chart instances for cleanup
const chartInstances = {};

function destroyChart(id) {
    // Stage 1: Explicit Tracking Cleanup
    if (chartInstances[id]) {
        try {
            // Only destroy if the instance is still valid
            if (typeof chartInstances[id].destroy === 'function') {
                chartInstances[id].destroy();
            }
        } catch (e) {
            console.warn(`Error destroying tracked chart "${id}":`, e);
        }
        delete chartInstances[id];
    }

    // Stage 2: DOM-based Search & Destroy (Nuclear Safety)
    // Sometimes charts are created without being stored in chartInstances
    const canvas = document.getElementById(id);
    if (canvas) {
        const existing = Chart.getChart(canvas);
        if (existing) {
            try {
                existing.destroy();
            } catch (e) {
                console.warn(`Error destroying DOM-found chart on "#${id}":`, e);
            }
        }
    }
}

function storeChart(id, chart) {
    destroyChart(id);
    chartInstances[id] = chart;
}

function resizeAllCharts() {
    Object.keys(chartInstances).forEach(id => {
        const chart = chartInstances[id];
        // Critical UX Bugfix: Ensure canvas is still in DOM before resizing.
        // Failing to check this causes the "ownerDocument of null" error when 
        // chartjs tries to measure a detached element during/after page transitions.
        if (chart && typeof chart.resize === 'function') {
            try {
                if (chart.canvas && document.body.contains(chart.canvas)) {
                    chart.resize();
                }
            } catch (e) {
                console.warn(`Suppressed resize error for chart "${id}":`, e);
            }
        }
    });
}
