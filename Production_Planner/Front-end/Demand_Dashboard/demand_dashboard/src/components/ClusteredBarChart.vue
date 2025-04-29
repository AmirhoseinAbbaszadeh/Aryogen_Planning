<!-- src/components/InventoryClusterChart.vue -->
<template>
    <Bar :data="chartData" :options="chartOpts" />
  </template>
  
  <script setup>
  import { Bar } from 'vue-chartjs'
  import {
    Chart,
    CategoryScale,
    LinearScale,
    BarElement,
    Tooltip,
    Legend,
  } from 'chart.js'
  
  // a lightweight, explicit register (tree-shakes unused stuff)
  Chart.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)
  
  const props = defineProps({
    /** [{ label:'2025-06', production:1600, invEnd:1600, demand:0 }, …] */
    series: { type: Array, required: true },
    title:  { type: String, default: 'Monthly Flow' },
  })
  
  /* build labels + three datasets */
  const labels        = props.series.map(r => r.label)
  const prodData      = props.series.map(r => r.production)
  const invEndData    = props.series.map(r => r.invEnd)
  const demandData    = props.series.map(r => r.demand)
  
  const chartData = {
    labels,
    datasets: [
      { label: 'Production',    data: prodData },
      { label: 'Inventory End', data: invEndData },
      { label: 'Demand',        data: demandData },
    ],
  }
  
  const chartOpts = {
    responsive: true,
    plugins: { title: { display: true, text: props.title } },
    scales:   { y: { beginAtZero: true } },
  }
  </script>
  