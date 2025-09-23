document.addEventListener("DOMContentLoaded", () => {
    /**
     * THEME: 다크/라이트 모드 관리
     * - localStorage에 사용자 선택 저장
     * - 테마 변경 시 모든 차트 다시 렌더링
     */
    Chart.register(ChartDataLabels);
    const THEME = {
        init() {
            const btn = document.getElementById("theme-toggle");
            if (!btn) return;
            const icon = btn.querySelector(".material-symbols-outlined");
            
            const applyTheme = (theme) => {
                document.documentElement.setAttribute("data-theme", theme);
                if (icon) icon.textContent = theme === "dark" ? "light_mode" : "dark_mode";
                localStorage.setItem("theme", theme);

                // 테마 변경 시 기존 차트 인스턴스 파괴
                if (window.riskTrendChartInstance) window.riskTrendChartInstance.destroy();
                if (window.sectorRiskChartInstance) window.sectorRiskChartInstance.destroy();
                if (window.riskGaugeChartInstance) window.riskGaugeChartInstance.destroy();
                
                // 잠시 후 모든 차트를 다시 그려 색상 설정을 올바르게 적용
                setTimeout(() => CHARTS.renderAll(), 100);
            };

            const currentTheme = localStorage.getItem("theme") || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
            applyTheme(currentTheme);
            btn.addEventListener("click", () => applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark"));
        }
    };

    /**
     * ANIMATIONS: 숫자 카운트업 효과
     * - 화면에 요소가 보일 때 한 번만 실행
     */
    const ANIMATIONS = {
        countUp() {
            const counters = document.querySelectorAll("[data-count]");
            const animate = (el) => {
                const target = parseFloat(el.getAttribute("data-count"));
                if (isNaN(target)) { el.textContent = el.getAttribute("data-count"); return; }
                
                // 애니메이션 시작 전 초기 텍스트에 '%'가 있는지 확인
                const isPercent = el.textContent.includes('%');
                const decimalPlaces = (target.toString().split('.')[1] || []).length;
                
                let start; 
                const duration = 1500; // 애니메이션 시간 (1.5초)
                
                const step = (timestamp) => {
                    if (!start) start = timestamp;
                    const progress = Math.min((timestamp - start) / duration, 1);
                    let current = progress * target;
    
                    // 애니메이션이 끝나면 목표 값으로 정확히 설정
                    if (progress === 1) {
                        current = target;
                    }
                    
                    // 최종 텍스트 구성
                    let text = current.toFixed(decimalPlaces);
                    if (isPercent) {
                        text += '%';
                    }
                    el.textContent = text;
                    
                    if (progress < 1) {
                        requestAnimationFrame(step);
                    }
                };
                requestAnimationFrame(step);
            };
    
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        animate(entry.target);
                        observer.unobserve(entry.target); // 한 번만 실행
                    }
                });
            }, { threshold: 0.5 });
            counters.forEach(counter => observer.observe(counter));
        }
    };

    /**
     * AI_REPORT: AI 리포트 비동기 생성
     * - 페이지 새로고침 없이 리포트 결과 업데이트
     */
    const AI_REPORT = {
        init() {
            const reportForm = document.getElementById("ai-report-form");
            if (!reportForm) return;

            reportForm.addEventListener("submit", async (e) => {
                e.preventDefault();
                
                const button = reportForm.querySelector("button");
                const buttonText = button.querySelector("span:last-child");
                const reportContent = document.getElementById("ai-report-content");

                button.disabled = true;
                if (buttonText) buttonText.textContent = "생성 중...";
                reportContent.innerHTML = `<p class="placeholder-text">AI가 리포트를 작성하고 있습니다...</p>`;
                
                try {
                    const response = await fetch(reportForm.action, { method: 'POST', headers: { 'Accept': 'text/html' } });
                    if (!response.ok) throw new Error(`서버 오류: ${response.statusText}`);
                    
                    const html = await response.text();
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    const newReportContent = doc.getElementById('ai-report-content');
                    
                    reportContent.innerHTML = newReportContent ? newReportContent.innerHTML : '<p class="placeholder-text">리포트를 불러오는 데 실패했습니다.</p>';
                } catch (error) {
                    reportContent.innerHTML = `<p class="placeholder-text" style="color:var(--color-danger)">오류 발생: ${error.message}</p>`;
                } finally {
                    button.disabled = false;
                    if (buttonText) buttonText.textContent = "리포트 생성";
                }
            });
        }
    };

    /**
     * CHARTS: 모든 Chart.js 관련 기능 관리
     */
    // CHARTS 객체 전체를 아래 코드로 교체하세요.
    const CHARTS = {
        getChartColors() {
            const style = getComputedStyle(document.documentElement);
            return {
                primary: style.getPropertyValue('--color-primary').trim(),
                danger: style.getPropertyValue('--color-danger').trim(),
                warning: style.getPropertyValue('--color-warning').trim(),
                success: style.getPropertyValue('--color-success').trim(),
                textSecondary: style.getPropertyValue('--color-text-secondary').trim(),
                border: style.getPropertyValue('--color-border').trim(),
                surface: style.getPropertyValue('--color-surface').trim()
            };
        },

        // CHARTS 객체 안의 renderRiskGaugeChart 함수를 이걸로 교체하세요.

        renderRiskGaugeChart() {
            const canvas = document.getElementById('riskGaugeChart');
            if (!canvas) return;

            if (window.riskGaugeChartInstance) {
                window.riskGaugeChartInstance.destroy();
            }

            const score = parseFloat(canvas.dataset.score);
            if (isNaN(score)) return;

            const statusEl = document.getElementById('riskGaugeStatus');
            const colors = this.getChartColors();
            let statusText, statusColor;

            // ✅ [수정] 3등분된 기준(33.3, 66.7)에 맞게 상태를 결정합니다.
            if (score >= 66.67) {
                statusText = '위험'; statusColor = colors.danger;
            } else if (score >= 33.33) {
                statusText = '주의'; statusColor = colors.warning;
            } else {
                statusText = '양호'; statusColor = colors.success;
            }

            if (statusEl) {
                statusEl.innerHTML = `
                    <div class="gauge-score-value">${score.toFixed(1)}</div>
                    <div class="gauge-status-text" style="color: ${statusColor};">${statusText}</div>
                `;
            }

            const data = {
                datasets: [
                    {
                        // ✅ [수정] 배경 게이지를 3등분합니다.
                        data: [33.33, 33.33, 33.34],
                        backgroundColor: [colors.success, colors.warning, colors.danger],
                        borderWidth: 0,
                    },
                    {
                        data: [score, 2, 100 - score - 2],
                        backgroundColor: ['transparent', colors.textPrimary, 'transparent'],
                        borderWidth: 0,
                    }
                ]
            };

            const config = {
                type: 'doughnut',
                data,
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    circumference: 180,
                    rotation: 270,
                    cutout: '60%', // ✅ 도넛을 더 두껍게 만듭니다 (65% -> 60%)
                    plugins: {
                        tooltip: { enabled: false },
                        legend: { display: false },
                        // ✅ [추가] 게이지 위 작은 회색 숫자를 제거합니다.
                        datalabels: {
                            display: false
                        }
                    },
                    animation: {
                        animateRotate: false
                    }
                }
            };
            window.riskGaugeChartInstance = new Chart(canvas, config);
        },

        // CHARTS 객체 안의 renderRiskTrendChart 함수를 이걸로 교체하세요.
        renderRiskTrendChart() {
            const canvas = document.getElementById('riskTrendChart');
            if (!canvas) return;
            const dataStr = canvas.dataset.chartData;
            if (!dataStr || dataStr === '{}') return;

            const data = JSON.parse(dataStr);
            const labels = Object.keys(data);
            const values = Object.values(data);
            const colors = this.getChartColors();

            const chartData = {
                labels,
                datasets: [{
                    label: '부실 확률',
                    data: values,
                    borderColor: colors.danger,
                    // ✅ [수정] 배경색을 반투명하게 변경 (예: 20% 불투명도)
                    backgroundColor: colors.danger + '33',
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: colors.surface,
                    pointBorderColor: colors.danger,
                    pointHoverRadius: 7,
                    pointRadius: 5
                }]
            };

            const config = {
                type: 'line',
                data: chartData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { ticks: { color: colors.textSecondary }, grid: { color: colors.border } },
                        y: { beginAtZero: true, ticks: { color: colors.textSecondary, callback: value => `${value}%` }, grid: { color: colors.border } }
                    },
                    // ✅ [수정] 플러그인 옵션 추가
                    plugins: {
                        legend: { display: false },
                        // 데이터 라벨 옵션
                        datalabels: {
                            align: 'end',     // 데이터 지점의 위쪽
                            anchor: 'end',    // 데이터 지점의 위쪽
                            color: colors.textSecondary,
                            font: {
                                weight: 'bold'
                            },
                            // 숫자를 '69.5%' 형태로 포맷팅
                            formatter: (value, context) => {
                                return value.toFixed(1) + '%';
                            }
                        }
                    }
                }
            };
            if(window.riskTrendChartInstance) window.riskTrendChartInstance.destroy();
            window.riskTrendChartInstance = new Chart(canvas, config);
        },

        // CHARTS 객체 안의 renderSectorRiskChart 함수를 이걸로 교체하세요.

        renderSectorRiskChart() {
            const container = document.getElementById('sectorRiskChart');
            if (!container) return;

            // 데이터 읽기
            const allDataEl = document.getElementById('sector-all-data');
            const highlightEl = document.getElementById('sector-highlight-label');
            if (!allDataEl || !highlightEl) return;
            
            const allData = JSON.parse(allDataEl.textContent);
            const highlightLabel = JSON.parse(highlightEl.textContent);

            // 필터 UI 요소
            const applyBtn = document.getElementById('sector-apply-filter');
            const keepHighlightCheck = document.getElementById('sector-keep-highlight');
            const dropdown = document.getElementById('sector-filter-dd');
            const summary = document.getElementById('sector-filter-summary');
            const clearBtn = document.getElementById('sector-filter-clear');
            const closeBtn = document.getElementById('sector-filter-close');
            const checkboxes = document.querySelectorAll('.sector-option');

            const colors = this.getChartColors();
            let chartInstance = null;

            // ✅ [추가] 업종명이 길 경우 두 줄로 바꿔주는 함수
            const wrapLabel = (label, maxLength = 10) => {
                if (label.length <= maxLength) return label;
                let splitIndex = label.lastIndexOf(' ', maxLength);
                if (splitIndex === -1) splitIndex = maxLength;
                return [label.substring(0, splitIndex), label.substring(splitIndex + 1)];
            };

            const updateChart = (selectedLabels) => {
                if (keepHighlightCheck.checked && !selectedLabels.includes(highlightLabel)) {
                    selectedLabels.push(highlightLabel);
                }

                const filteredData = allData
                    .filter(d => selectedLabels.includes(d.label))
                    .sort((a, b) => b.value - a.value);

                if (chartInstance) {
                    chartInstance.destroy();
                }

                const chartData = {
                    // ✅ [수정] 라벨 생성 시 wrapLabel 함수 적용
                    labels: filteredData.map(d => wrapLabel(d.label)),
                    datasets: [{
                        label: '부실 징후 확률',
                        data: filteredData.map(d => d.value * 100),
                        backgroundColor: filteredData.map(d => d.label === highlightLabel ? colors.success : colors.primary),
                        borderRadius: 4
                    }]
                };

                const config = {
                    type: 'bar',
                    data: chartData,
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { 
                            legend: { display: false }, 
                            datalabels: { 
                                color: colors.surface, 
                                anchor: 'end', 
                                align: 'start', 
                                formatter: val => val.toFixed(1) + '%' 
                            } 
                        },
                        scales: {
                            // ✅ [수정] x축의 최대값을 100으로 변경
                            x: { beginAtZero: true, max: 100, ticks: { color: colors.textSecondary, callback: value => `${value}%` }, grid: { color: colors.border } },
                            y: { ticks: { color: colors.textSecondary }, grid: { display: false } }
                        }
                    }
                };
                chartInstance = new Chart(container, config);
                window.sectorRiskChartInstance = chartInstance;
            };

            const getSelected = () => Array.from(checkboxes).filter(cb => cb.checked).map(cb => cb.value);

            const updateSummaryText = () => {
                const count = getSelected().length;
                summary.textContent = `대분류 선택 (${count}개)`;
            };
            
            // 이벤트 리스너 설정
            applyBtn.addEventListener('click', () => {
                updateChart(getSelected());
                dropdown.open = false;
            });
            
            clearBtn.addEventListener('click', () => {
                checkboxes.forEach(cb => cb.checked = false);
                updateSummaryText();
            });
            closeBtn.addEventListener('click', () => dropdown.open = false);
            checkboxes.forEach(cb => cb.addEventListener('change', updateSummaryText));
            
            // 초기 차트 렌더링
            const initChart = () => {
                const defaultLabels = new Set();
                if (highlightLabel) {
                    defaultLabels.add(highlightLabel);
                }
                for (const item of allData) {
                    if (defaultLabels.size >= 4) break;
                    defaultLabels.add(item.label);
                }
                const initialLabels = Array.from(defaultLabels);
                checkboxes.forEach(cb => {
                    cb.checked = initialLabels.includes(cb.value);
                });
                updateSummaryText();
                updateChart(initialLabels);
            };

            initChart();
        },

        renderBenchmarkCharts() {
            const chartCanvases = document.querySelectorAll('.benchmark-bar-chart');
            if (chartCanvases.length === 0) return;
            
            const colors = this.getChartColors();
        
            chartCanvases.forEach((canvas, index) => {
                const companyValue = parseFloat(canvas.dataset.companyValue);
                const industryValue = parseFloat(canvas.dataset.industryValue);
        
                const data = {
                    labels: ['', ''],
                    datasets: [{
                        data: [companyValue, industryValue],
                        backgroundColor: [colors.primary, '#bdc1c6'],
                        borderRadius: 4,
                        barPercentage: 0.9,
                        categoryPercentage: 1.0,
                    }]
                };
        
                const config = {
                    type: 'bar',
                    data: data,
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: { enabled: true },
                            datalabels: {
                                // ✅ [수정] 막대 길이에 따라 숫자 위치와 색상을 동적으로 변경
                                anchor: 'end',
                                align: (context) => {
                                    const value = context.dataset.data[context.dataIndex];
                                    const maxValue = Math.max(companyValue, industryValue) * 1.1; // 축 최대값 추정
                                    return value > maxValue * 0.8 ? 'start' : 'end'; // 막대가 80% 이상 길면 안쪽(start)에 표시
                                },
                                offset: 4,
                                formatter: (value) => value.toFixed(1),
                                font: { weight: '500' },
                                color: (context) => {
                                    const value = context.dataset.data[context.dataIndex];
                                    const maxValue = Math.max(companyValue, industryValue) * 1.1;
                                    // 안쪽에 표시될 때 흰색, 바깥쪽일 때 원래 색상
                                    return value > maxValue * 0.8 ? colors.surface : colors.textPrimary;
                                }
                            }
                        },
                        scales: {
                            x: { 
                                display: false, 
                                beginAtZero: true,
                                // ✅ [추가] 차트 오른쪽에 여유 공간을 10% 줘서 숫자가 잘리지 않게 함
                                grace: '10%' 
                            },
                            y: { display: false }
                        }
                    }
                };
        
                const chartId = `benchmarkChart_${index}`;
                if (window[chartId]) window[chartId].destroy();
                window[chartId] = new Chart(canvas, config);
            });
        },

        renderAll() {
            this.renderRiskGaugeChart();
            this.renderRiskTrendChart();
            this.renderSectorRiskChart();
            this.renderBenchmarkCharts();
            // benish 차트는 JS로 그리지 않으므로 여기서 호출하지 않습니다.
        }
    };
    
    // --- 페이지 초기화 실행 ---
    THEME.init();
    ANIMATIONS.countUp();
    AI_REPORT.init();
    CHARTS.renderAll();
});