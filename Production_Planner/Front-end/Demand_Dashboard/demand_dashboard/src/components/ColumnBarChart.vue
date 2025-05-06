<template>
  <div class="chart-card" v-if="labels.length">
    <h2>Inventory / Production / Demand</h2>
    <canvas ref="canvasEl"></canvas>
  </div>
  <p v-else class="text-muted">No inventory summary available to chart.</p>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue';
import { Chart, registerables } from 'chart.js';
Chart.register(...registerables);

// --- Custom plugin to draw month separators ---
const monthSeparatorPlugin = {
  id: 'monthSeparator',
  afterDraw(chart) {
    const { ctx, scales: { x, y } } = chart;
    let prevMonth = null;

    chart.data.labels.forEach((label, i) => {
      // parse the start date
      const startDate = new Date(label.split(' to ')[0]);
      const thisMonth = startDate.getFullYear() + '-' + (startDate.getMonth() + 1);

      if (prevMonth !== null && thisMonth !== prevMonth) {
        const xPos = x.getPixelForValue(i - 0.5);
        ctx.save();
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = 'gray';
        ctx.beginPath();
        ctx.moveTo(xPos, y.top);
        ctx.lineTo(xPos, y.bottom);
        ctx.stroke();
        ctx.restore();
      }

      prevMonth = thisMonth;
    });
  }
};

// Register the plugin
Chart.register(monthSeparatorPlugin);

// Props & reactive state
const props = defineProps({
  linesdetail: { type: String, required: true }
});

const canvasEl = ref(null);
let chart = null;
const labels = ref([]);
const demandData = ref([]);
const prodData = ref([]);
const invStartData = ref([]);
const invEndData = ref([]);

// parse the input text into arrays
function parseLinesDetail(text) {
  const lineRe = /^(\d{4}-\d{2}-\d{2})\s*[-–]\s*(\d{4}-\d{2}-\d{2})/;
  labels.value = [];
  demandData.value = [];
  prodData.value = [];
  invStartData.value = [];
  invEndData.value = [];

  text.split('\n').forEach(raw => {
    const line = raw.trim();
    const m = line.match(lineRe);
    if (!m) return;

    labels.value.push(`${m[1]} to ${m[2]}`);

    const cols = line.split(/\s+/);
    demandData.value.push(parseFloat(cols[3]));
    prodData.value.push(parseFloat(cols[4]));
    invStartData.value.push(parseFloat(cols[5]));
    invEndData.value.push(parseFloat(cols[6]));
  });
}

// render (or re-render) the chart
function renderChart() {
  const ctx = canvasEl.value?.getContext('2d');
  if (!ctx) return;

  if (chart) chart.destroy();

  chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels.value,
      datasets: [
        { label: 'Inventory Start', data: invStartData.value, backgroundColor: 'rgba(54,99,192,0.5)' },
        { label: 'Production',      data: prodData.value,   backgroundColor: 'rgba(54,162,235,0.5)' },
        { label: 'Demand',          data: demandData.value, backgroundColor: 'rgba(255,99,132,0.5)' },
        { label: 'Inventory End',   data: invEndData.value, backgroundColor: 'rgba(75,192,192,0.5)' },
      ]
    },
    options: {
      responsive: true,
      scales: {
        x: {
          stacked: false,
          ticks: { autoSkip: true, maxRotation: 0, padding: 10 },
          offset: true,
          barPercentage: 0.2,
          categoryPercentage: 0.3
        },
        y: { beginAtZero: true }
      },
      layout: {
        padding: { top: 30 }
      },
      plugins: {
        legend: { position: 'top' },
        monthSeparator: {}  // enable our custom plugin
      }
    },
    plugins: [ monthSeparatorPlugin ]  // register it per-chart
  });
}

// initial mount
onMounted(async () => {
  parseLinesDetail(props.linesdetail);
  await nextTick();
  renderChart();
});

// watch for updates
watch(() => props.linesdetail, async (newVal) => {
  parseLinesDetail(newVal);
  await nextTick();
  renderChart();
});
</script>

<style scoped>
.chart-card {
  background: #fff;
  padding: 1rem;
  border-radius: 8px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
  margin-bottom: 2rem;
}

.chart-card h2 {
  margin-bottom: 0.5rem;
}

.text-muted {
  color: #666;
  font-style: italic;
}
</style>
