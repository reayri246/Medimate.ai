document.addEventListener('DOMContentLoaded', function () {
  const navLinks = document.querySelectorAll('.nav-link');
  navLinks.forEach(function (link) {
    if (link.getAttribute('href') && link.getAttribute('href').startsWith('#')) {
      link.addEventListener('click', function (event) {
        const target = document.querySelector(link.getAttribute('href'));
        if (target) {
          event.preventDefault();
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    }
  });

  document.querySelectorAll('[data-assistant-prompt]').forEach(function (button) {
    button.addEventListener('click', function () {
      const question = document.getElementById('id_question');
      if (question) {
        question.value = button.dataset.assistantPrompt;
        question.focus();
      }
    });
  });

  const notificationAudienceInputs = document.querySelectorAll('input[name="audience"]');
  const notificationRecipientField = document.querySelector('[data-notification-recipient]');
  if (notificationAudienceInputs.length && notificationRecipientField) {
    const updateNotificationRecipientVisibility = function () {
      const individualSelected = Array.from(notificationAudienceInputs).some(function (input) {
        return input.checked && input.value === 'selected';
      });
      notificationRecipientField.hidden = !individualSelected;
    };
    notificationAudienceInputs.forEach(function (input) {
      input.addEventListener('change', updateNotificationRecipientVisibility);
    });
    updateNotificationRecipientVisibility();
  }

  const chartElement = document.getElementById('measurementChart');
  const chartDataElement = document.getElementById('measurement-chart-data');
  if (chartElement && chartDataElement && typeof Chart !== 'undefined') {
    const data = JSON.parse(chartDataElement.textContent);
    new Chart(chartElement, {
      type: 'line',
      data: {
        labels: data.labels,
        datasets: [
          {
            label: 'Systolic blood pressure (mmHg)',
            data: data.systolic,
            borderColor: '#19ad8e',
            backgroundColor: 'rgba(25, 173, 142, .1)',
            pointBackgroundColor: '#19ad8e',
            pointRadius: 3,
            borderWidth: 2,
            tension: .35,
            spanGaps: true,
            yAxisID: 'y',
          },
          {
            label: 'Heart rate (bpm)',
            data: data.heart_rate,
            borderColor: '#4397ee',
            backgroundColor: 'rgba(67, 151, 238, .08)',
            pointBackgroundColor: '#4397ee',
            pointRadius: 3,
            borderWidth: 2,
            tension: .35,
            spanGaps: true,
            yAxisID: 'y1',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: { backgroundColor: '#153c4a', padding: 10, usePointStyle: true },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: '#81939b', font: { size: 10 } },
            border: { display: false },
          },
          y: {
            type: 'linear',
            position: 'left',
            beginAtZero: false,
            grid: { color: '#edf2f3' },
            ticks: { color: '#81939b', font: { size: 10 } },
            border: { display: false },
          },
          y1: {
            type: 'linear',
            position: 'right',
            beginAtZero: false,
            grid: { drawOnChartArea: false },
            ticks: { color: '#81939b', font: { size: 10 } },
            border: { display: false },
          },
        },
      },
    });
  }
});
