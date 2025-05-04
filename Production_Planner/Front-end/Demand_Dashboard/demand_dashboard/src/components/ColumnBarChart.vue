<template>
  <div class="chart-card" v-if="labels.length">
    <h2>Inventory / Production / Demand</h2>
    <!-- Static ref name: canvasEl -->
    <canvas ref="canvasEl"></canvas>
  </div>
  <p v-else class="text-muted">No inventory summary available to chart.</p>
</template>

<script setup>
/* eslint-disable */
import { ref, watch, onMounted, nextTick } from 'vue';
import { Chart, registerables } from 'chart.js';
Chart.register(...registerables);

// Accept raw text
const props = defineProps({
  linesdetail: { type: String, required: true }
});

// Refs and data arrays
const canvasEl = ref(null);
let chart = null;
const labels = ref([]);
const demandData = ref([]);
const prodData = ref([]);
const invEndData = ref([]);
const invStartData = ref([]);

// Parse the table text into arrays
function parseLinesDetail(text) {
  const lineRe = /^(\d{4}-\d{2}-\d{2})\s*[-–]\s*(\d{4}-\d{2}-\d{2})/;

  labels.value = [];
  demandData.value = [];
  prodData.value = [];
  invEndData.value = [];
  invStartData.value = [];

  text.split('\n').forEach(raw => {
    const line = raw.trim();
    const m = line.match(lineRe);
    if (!m) return;           // skip any non-matching line

    // m[1] is the start date, m[2] is the end date
    labels.value.push(`${m[1]} to ${m[2]}`);

    // now split off the rest of the numeric columns:
    const cols = line.split(/\s+/);
    // based on your layout: cols[3]=Demand, [4]=NewProd, [6]=InvEnd
    demandData.value.push(parseFloat(cols[3]));
    prodData.value.push(parseFloat(cols[4]));
    invStartData.value.push(parseFloat(cols[5]));
    invEndData.value.push(parseFloat(cols[6]));
  });
}

// Create or update the Chart.js instance
function renderChart() {
  const ctx = canvasEl.value?.getContext('2d');
  if (!ctx) return;

  if (chart) {
    chart.destroy();
  }
  chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels.value,
      datasets: [
        { label: 'Inventory Start', data: invStartData.value, backgroundColor: 'rgba(54,99,192,0.5)' },
        { label: 'Production', data: prodData.value, backgroundColor: 'rgba(54,162,235,0.5)' },
        { label: 'Demand', data: demandData.value, backgroundColor: 'rgba(255,99,132,0.5)' },
        { label: 'Inventory End', data: invEndData.value, backgroundColor: 'rgba(75,192,192,0.5)' },
      ]
    },
    options: {
      responsive: true,
      scales: {
        x: { stacked: false, ticks: { autoSkip: true, maxRotation: 0},
          offset: true,              // adds space at the start and end of the scale
          barPercentage: 0.2,        // adjust the width of the bars
          categoryPercentage: 0.3,
        },
        y: { beginAtZero: true}
      },
      layout: {
        padding: {
          top: 30   // ← 30px of space above the highest bars
        }
      },
      plugins: { legend: { position: 'top' } }
    }
  });
}

// Wait for DOM to update before drawing
onMounted(async () => {
  parseLinesDetail(props.linesdetail);
  await nextTick();
  renderChart();
});

// Re-parse & re-render when the text changes
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