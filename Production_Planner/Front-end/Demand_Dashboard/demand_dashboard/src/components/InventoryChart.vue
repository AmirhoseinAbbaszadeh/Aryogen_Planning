<template>
  <div ref="inventoryChart" class="chart-container"></div>
</template>

<script>
import Plotly from 'plotly.js-dist-min';

export default {
  name: 'InventoryChart',
  props: {
    // { productName: { monthNumber: inventoryValue, … }, … }
    inventoryData: {
      type: Object,
      required: true
    }
  },
  mounted() {
    this.drawInventoryChart();
  },
  watch: {
    inventoryData: {
      handler() {
        this.drawInventoryChart();
      },
      deep: true
    }
  },
  methods: {
    drawInventoryChart() {
      Plotly.purge(this.$refs.inventoryChart);

      if (!this.inventoryData || Object.keys(this.inventoryData).length === 0) {
        console.warn('InventoryChart: no data');
        return;
      }

      const traces = [];
      const annotations = [];

      Object.entries(this.inventoryData).forEach(([product, monthMap]) => {
        const months = Object.keys(monthMap)
          .map(n => parseInt(n, 10))
          .sort((a, b) => a - b);
        const x = months.map(m => `Month ${m}`);
        const y = months.map(m => monthMap[m]);

        // Build the trace
        traces.push({
          x,
          y,
          mode: 'lines+markers',
          name: product,
          line: { width: 3 },
          marker: { size: 6 }
        });

        // Add annotation at the last point
        const lastX = x[x.length - 1];
        const lastY = y[y.length - 1];
        annotations.push({
          x: lastX,
          y: lastY,
          xref: 'x',
          yref: 'y',
          text: product,
          showarrow: false,
          xanchor: 'left',
          font: { size: 12 }
        });
      });

      const layout = {
        title: 'Inventory Trajectory by Product',
        xaxis: {
          title: 'Month',
          tickangle: -45
        },
        yaxis: {
          title: 'Inventory Level'
        },
        legend: {
          orientation: 'v',
          x: 1.02,
          y: 1,
          traceorder: 'normal'
        },
        annotations,
        margin: { l: 60, r: 140, t: 60, b: 100 },
        height: 500
      };

      Plotly.newPlot(this.$refs.inventoryChart, traces, layout, { responsive: true });
    }
  }
};
</script>

<style scoped>
.chart-container {
  width: 100%;
  height: 500px;
}
</style>
