document.addEventListener('DOMContentLoaded', () => {
    const inputTicker = document.getElementById('ticker-input');
    const btnAnalyze = document.getElementById('btn-analyze');

    // States
    const stateWelcome = document.getElementById('welcome-state');
    const stateLoading = document.getElementById('loading-state');
    const stateError = document.getElementById('error-state');
    const stateDashboard = document.getElementById('dashboard-state');
    const errorMsg = document.getElementById('error-msg');

    let currentTicker = null;
    let revChartInstance = null;
    let marginChartInstance = null;
    let returnsChartInstance = null;
    let liquidityChartInstance = null;
    let efficiencyChartInstance = null;
    let cashConversionChartInstance = null;
    let monteCarloChartInstance = null;

    btnAnalyze.addEventListener('click', () => {
        const ticker = inputTicker.value.trim().toUpperCase();
        if (!ticker) return;
        fetchData(ticker);
    });

    inputTicker.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            btnAnalyze.click();
        }
    });

    async function fetchData(ticker) {
        showState('loading');
        currentTicker = ticker;

        try {
            const res = await fetch(`/api/analyze?ticker=${ticker}`);
            const data = await res.json();

            if (res.ok && data.status === 'success') {
                populateDashboard(data);
                showState('dashboard');
            } else {
                throw new Error(data.detail || data.message || 'Analysis failed');
            }
        } catch (error) {
            errorMsg.innerText = error.message;
            showState('error');
        }
    }

    function populateDashboard(data) {
        // Text Binding
        document.getElementById('company-name').innerText = data.ticker + " Financials";
        document.getElementById('company-ticker').innerText = data.ticker;

        // Populate Standard KPIs
        document.getElementById('kpi-ebitda').innerText = data.kpis?.ebitda || "N/A";
        document.getElementById('kpi-roe').innerText = data.kpis?.roe || "N/A";
        document.getElementById('kpi-de').innerText = data.kpis?.de || "N/A";
        document.getElementById('kpi-fcf').innerText = data.kpis?.fcf || "N/A";

        // Populate Valuation & R&D Metrics (Added based on instruction)
        document.getElementById('kpi-runway').innerText = data.valuation?.runway || "N/A";
        document.getElementById('kpi-burn-rate').innerText = data.valuation?.burn_rate || "N/A";
        document.getElementById('kpi-npv').innerText = data.valuation?.npv || "N/A";

        // AI Summary
        document.getElementById('ai-summary').innerText = data.ai_summary || "Summary not generated.";

        // Charts
        renderCharts(data);
    }

    function renderCharts(data) {
        // Destroy existing for clean redraw
        if (revChartInstance) revChartInstance.destroy();
        if (marginChartInstance) marginChartInstance.destroy();
        if (returnsChartInstance) returnsChartInstance.destroy();
        if (liquidityChartInstance) liquidityChartInstance.destroy();
        if (efficiencyChartInstance) efficiencyChartInstance.destroy();
        if (cashConversionChartInstance) cashConversionChartInstance.destroy();
        if (monteCarloChartInstance) monteCarloChartInstance.destroy();

        const commonOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' }
            }
        };

        const revCtx = document.getElementById('revChart').getContext('2d');
        revChartInstance = new Chart(revCtx, {
            type: 'bar',
            data: {
                labels: data.years || [],
                datasets: [{
                    label: 'Total Revenue',
                    data: data.revenue_trend || [],
                    backgroundColor: '#2563eb',
                    borderRadius: 4
                }]
            },
            options: commonOptions
        });

        const marginCtx = document.getElementById('marginChart').getContext('2d');
        marginChartInstance = new Chart(marginCtx, {
            type: 'line',
            data: {
                labels: data.years || [],
                datasets: [
                    {
                        label: 'Gross Margin (%)',
                        data: data.gross_margins || [],
                        borderColor: '#0ea5e9',
                        tension: 0.3,
                        fill: false
                    },
                    {
                        label: 'EBITDA Margin (%)',
                        data: data.ebitda_margins || [],
                        borderColor: '#16a34a',
                        backgroundColor: 'rgba(22, 163, 74, 0.1)',
                        tension: 0.3,
                        fill: true
                    },
                    {
                        label: 'EBIT Margin (%)',
                        data: data.ebit_margins || [],
                        borderColor: '#f59e0b',
                        tension: 0.3,
                        fill: false
                    },
                    {
                        label: 'Net Margin (%)',
                        data: data.net_margins || [],
                        borderColor: '#ef4444',
                        tension: 0.3,
                        fill: false
                    }
                ]
            },
            options: commonOptions
        });

        const returnsCtx = document.getElementById('returnsChart').getContext('2d');
        returnsChartInstance = new Chart(returnsCtx, {
            type: 'bar',
            data: {
                labels: data.years || [],
                datasets: [
                    {
                        label: 'ROA (%)',
                        data: data.roa || [],
                        backgroundColor: '#8b5cf6',
                        borderRadius: 4
                    }
                ]
            },
            options: commonOptions
        });

        const liquidityCtx = document.getElementById('liquidityChart').getContext('2d');
        liquidityChartInstance = new Chart(liquidityCtx, {
            type: 'line',
            data: {
                labels: data.years || [],
                datasets: [
                    {
                        label: 'Current Ratio',
                        data: data.current_ratios || [],
                        borderColor: '#3b82f6',
                        tension: 0.3,
                        fill: false
                    },
                    {
                        label: 'Quick Ratio',
                        data: data.quick_ratios || [],
                        borderColor: '#10b981',
                        tension: 0.3,
                        fill: false
                    }
                ]
            },
            options: commonOptions
        });

        const efficiencyCtx = document.getElementById('efficiencyChart').getContext('2d');
        efficiencyChartInstance = new Chart(efficiencyCtx, {
            type: 'bar',
            data: {
                labels: data.years || [],
                datasets: [
                    {
                        label: 'Asset Turnover',
                        data: data.asset_turnover || [],
                        backgroundColor: '#f97316',
                        borderRadius: 4
                    }
                ]
            },
            options: commonOptions
        });

        const cashConversionCtx = document.getElementById('cashConversionChart').getContext('2d');
        cashConversionChartInstance = new Chart(cashConversionCtx, {
            type: 'bar',
            data: {
                labels: data.years || [],
                datasets: [
                    {
                        label: 'Cash Conversion Ratio',
                        data: data.cash_conversion || [],
                        backgroundColor: '#14b8a6',
                        borderRadius: 4
                    }
                ]
            },
            options: commonOptions
        });

        // --- Monte Carlo Price Simulation Chart ---
        if (data.monte_carlo) {
            const mcCtx = document.getElementById('monteCarloChart');
            if (mcCtx) {
                const daysLabel = Array.from({ length: 252 }, (_, i) => `Day ${i}`);

                monteCarloChartInstance = new Chart(mcCtx.getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: daysLabel,
                        datasets: [
                            {
                                label: 'Bull Case (90th Percentile)',
                                data: data.monte_carlo.p90_path,
                                borderColor: 'rgba(16, 185, 129, 0.6)', // Green
                                borderDash: [5, 5],
                                borderWidth: 1,
                                tension: 0.1,
                                fill: false,
                                pointRadius: 0
                            },
                            {
                                label: 'Mean Forecast Path',
                                data: data.monte_carlo.mean_path,
                                borderColor: 'rgba(59, 130, 246, 1)', // Solid Blue
                                borderWidth: 2,
                                tension: 0.1,
                                fill: false,
                                pointRadius: 0
                            },
                            {
                                label: 'Bear Case (10th Percentile)',
                                data: data.monte_carlo.p10_path,
                                borderColor: 'rgba(239, 68, 68, 0.6)', // Red
                                borderDash: [5, 5],
                                borderWidth: 1,
                                tension: 0.1,
                                fill: false,
                                pointRadius: 0
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'bottom' },
                            title: {
                                display: true,
                                text: `Monte Carlo Pricing Forecast (Last: ${data.currency}${data.monte_carlo.last_price.toFixed(2)})`
                            }
                        },
                        scales: {
                            y: {
                                ticks: {
                                    callback: function (value) {
                                        return data.currency + value;
                                    }
                                }
                            }
                        }
                    }
                });
            }
        }
    }

    // Download Handler
    document.getElementById('btn-download').addEventListener('click', () => {
        if (!currentTicker) return;
        window.location.href = `/api/download?ticker=${currentTicker}`;
    });

    function showState(stateName) {
        stateWelcome.style.display = 'none';
        stateLoading.style.display = 'none';
        stateError.style.display = 'none';
        stateDashboard.style.display = 'none';

        if (stateName === 'welcome') stateWelcome.style.display = 'flex';
        if (stateName === 'loading') stateLoading.style.display = 'flex';
        if (stateName === 'error') stateError.style.display = 'flex';
        if (stateName === 'dashboard') stateDashboard.style.display = 'block';
    }
});
