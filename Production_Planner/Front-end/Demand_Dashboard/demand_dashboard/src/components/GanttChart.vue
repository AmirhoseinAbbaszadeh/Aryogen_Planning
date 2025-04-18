<template>
    <div ref="chartContainer" class="chart-container"></div>
  </template>
  
  <script>
  import Plotly from 'plotly.js-dist-min';
  
  export default {
    name: 'GanttStepChart',
    props: {
      // planData is an array of production run objects.
      // Each run must have 'product', 'run_index', and an array 'br_stages'.
      // Each stage should contain 'stage', 'start_date', and 'end_date'.
      planData: {
        type: Array,
        required: true
      }
    },
    mounted() {
      this.renderChart();
    },
    watch: {
      planData() {
        this.renderChart();
      }
    },
    methods: {
      renderChart() {
        if (!this.planData.length) {
          console.warn('No planData provided.');
          return;
        }
  
        // Sort runs by product and run_index.
        const runs = [...this.planData].sort((a, b) => {
          if (a.product === b.product) {
            return a.run_index - b.run_index;
          }
          return a.product.localeCompare(b.product);
        });
        
        const traces = [];
        const yTickVals = [];
        const yTickLabels = [];
        const runSpacing = 60; // spacing between runs
  
        runs.forEach((run, runIdx) => {
          // The base y position for the run.
          const baseY = runIdx * runSpacing;
          if (!run.br_stages || !run.br_stages.length) return;
          
          run.br_stages.forEach((stage, stageIdx) => {
            // Calculate the y value for each stage (stepped downward for each subsequent stage).
            const yValue = baseY - stageIdx;
            
            // Parse stage start and end dates.
            const startDate = new Date(stage.start_date);
            const endDate = new Date(stage.end_date);
            if (isNaN(startDate) || isNaN(endDate)) {
              console.warn('Invalid date found in stage:', stage);
              return;
            }
            // If start and end are the same (or too close), add one day to ensure a visible line.
            let adjustedEndDate = endDate;
            if (Math.abs(endDate.getTime() - startDate.getTime()) < 1000) {
              adjustedEndDate = new Date(startDate);
              adjustedEndDate.setDate(adjustedEndDate.getDate() + 1);
            }
            const x0 = startDate.toISOString();
            const x1 = adjustedEndDate.toISOString();
            
            // Log for debugging.
            console.log(`Run ${run.product} #${run.run_index} Stage "${stage.stage}":`, x0, 'to', x1);
            
            // Create the trace for this stage.
            traces.push({
              x: [x0, x1],
              y: [yValue, yValue],
              type: 'scatter',
              mode: 'lines+markers',
              marker: {
                size: 8,
                color: stage.color
              },
              line: {
                width: 20,
                shape: 'hv'
              },
              hoverinfo: 'text',
              text: `${stage.stage}<br>${x0} to ${x1}`
            });
            // Save the y value and label for the y-axis.
            yTickVals.push(yValue);
            yTickLabels.push(`${run.product} - Run ${run.run_index}: ${stage.stage}`);
          });
        });
        
        const layout = {
          title: 'Production Timeline - Stepped Gantt Chart',
          xaxis: {
            type: 'date',
            title: 'Date'
          },
          yaxis: {
            tickmode: 'array',
            tickvals: yTickVals,
            ticktext: yTickLabels,
            automargin: true
          },
          height: 600,
          margin: { l: 300, r: 50, t: 80, b: 50 }
        };
        
        Plotly.newPlot(this.$refs.chartContainer, traces, layout);
      }
    }
  };
  </script>
  
  <style scoped>
  .chart-container {
    width: 100%;
  }
  </style>
  