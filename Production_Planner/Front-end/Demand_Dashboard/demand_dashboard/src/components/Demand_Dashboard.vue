<template>
  <div class="container">
    <h1 class="title">Full Production Planning Scheduler (Dynamic Products & Doses)</h1>

    <form @submit.prevent="submitPlan">

      <!-- SECTION SELECTOR -->
      <div class="card">
        <label for="sectionSelect"><strong>Select Section:</strong></label>
        <select id="sectionSelect" v-model="selectedSection">
          <option value="productsDoses">Products & Doses</option>
          <option value="currentStock">Current Stock</option>
          <option value="busyLines">Busy Lines</option>
        </select>
      </div>

      <!-- 1) PRODUCTS & DOSES -->
      <div v-if="selectedSection === 'productsDoses'">
        <div class="card">
          <h2>Products & Doses</h2>
          <!-- Top-Level Product Selector -->
          <div class="selector-panel">
            <label for="productSelect"><strong>Select Product:</strong></label>
            <select id="productSelect" v-model.number="selectedProductIndex">
              <option v-for="(product, idx) in products" :key="idx" :value="idx">
                {{ product.name || ("Unnamed Product " + (idx + 1)) }}
              </option>
            </select>
            <!-- Add/Remove buttons -->
            <div class="selector-buttons">
              <button type="button" class="add-btn small" @click="addProduct">+ Add Product</button>
              <button type="button" class="remove-btn small" :disabled="products.length === 0" @click="removeSelectedProduct">
                Remove Product
              </button>
            </div>
          </div>
          <!-- Show the selected product's details -->
          <div v-if="currentProduct" class="product-entry">
            <div class="product-header">
              <h3>Product {{ currentProduct.name || 'Unnamed' }}</h3>
            </div>
            <label>Product Name:</label>
            <input type="text" v-model="currentProduct.name" placeholder="e.g., E, B, X..." @input="syncCommonBRs" />

            <!-- Doses for the selected product -->
            <div v-for="(dose, doseIndex) in currentProduct.doses" :key="doseIndex" class="dose-entry">
              <div class="dose-header">
                <h4>Dose: {{ dose.name || 'Unnamed' }}</h4>
                <button type="button" class="remove-btn small" @click="removeDose(doseIndex)">Remove Dose</button>
              </div>
              <label>Dose Name:</label>
              <input type="text" v-model="dose.name" placeholder="e.g. a, b, x, y..." @input="syncCommonBRs" />
              <br>
              <!-- Export & Sales monthly requirements + sum for each month -->
              <div class="month-stocks">
                <h5>Export Monthly Stock Requirements</h5>
                <div class="month-grid">
                  <div v-for="month in 15" :key="'export-' + month" class="month-entry">
                    <label>Month {{ month }}:</label>
                    <input type="number" v-model.number="dose.exportMinStocks[month]" placeholder="Export stock" />
                  </div>
                </div>
              </div>
              <br>
              <div class="month-stocks">
                <h5>Sales Monthly Stock Requirements</h5>
                <div class="month-grid">
                  <div v-for="month in 15" :key="'sales-' + month" class="month-entry">
                    <label>Month {{ month }}:</label>
                    <input type="number" v-model.number="dose.salesMinStocks[month]" placeholder="Sales stock" />
                  </div>
                </div>
              </div>
              <br>
              <!-- Display the total for each month (export + sales) -->
              <div class="month-stocks">
                <h5>Total Monthly Requirement</h5>
                <div class="month-grid">
                  <div v-for="month in 15" :key="'total-' + month" class="month-entry">
                    <label>Month {{ month }}:</label>
                    <input type="number" :value="dose.exportMinStocks[month] + dose.salesMinStocks[month]" disabled />
                  </div>
                </div>
              </div>
              <br>
            </div>
            <!-- Add Dose Button -->
            <button type="button" class="add-btn small" @click="addDose">+ Add Dose</button>
          </div>
        </div>
      </div>

      <!-- 3) CURRENT STOCK -->
      <div v-if="selectedSection === 'currentStock'">
        <div class="card">
          <h2>Current Stock</h2>
          <p class="info">
            Select a product-dose (only those with entered monthly demand), enter the current amount, and specify the expiration offset.
          </p>
          <!-- Display the globally selected date -->
          <div class="selected-date">
            <div>
                <strong>
                    Selected Date => &nbsp;
                    <span>
                      <span v-if="selectedDate">{{ selectedDate }}</span>
                      <span v-else style="color: red;">No date selected. Please Select the Production Date.</span>
                    </span>
                </strong>
            </div>
          </div>
          <div v-for="(entry, idx) in currentStocks" :key="idx" class="current-stock-entry">
            <label>Product & Dose:</label>
            <select v-model="entry.productDose">
              <option disabled value="">Select Product & Dose</option>
              <option v-for="option in demandedProductOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
            <label>Current Amount:</label>
            <input type="number" v-model.number="entry.amount" placeholder="Current amount" />
            
            <label>Expiration Offset (months):</label>
            <input type="number" v-model.number="entry.expirationOffsetMonths" placeholder="Enter offset in months" />

            <label>Expiration Offset (days):</label>
            <input type="number" v-model.number="entry.expirationOffsetDays" placeholder="Enter offset in days" />
            
            <div class="calculated-expiration">
              <strong>Calculated Expiration Date => &nbsp;</strong>
              <span>
                {{ calculateExpiration(selectedDate, entry.expirationOffsetMonths, entry.expirationOffsetDays) || 'N/A' }}
              </span>
            </div>
            <button type="button" class="remove-btn small" @click="removeCurrentStock(idx)">Remove</button>
          </div>
          <button type="button" class="add-btn" @click="addCurrentStock">+ Add Current Stock Entry</button>
        </div>
      </div>

      <!-- Busy Lines Section -->
      <div v-if="selectedSection === 'busyLines'" class="card">
        <h2>Busy Lines</h2>
        <p class="info">
          Select a busy line (from the available lines) and enter its finish offset in months and days.
        </p>
        <div v-for="(entry, idx) in busyLines" :key="idx" class="busy-line-entry">
          <label>Line:</label>
          <select v-model="entry.line">
            <option disabled value="">Select Busy Line</option>
            <option v-for="option in availableLines" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>

            <label>Finish Offset (months):</label>
            <input type="number" v-model.number="entry.finishOffsetMonths" placeholder="Offset months" />

            <label>Finish Offset (days):</label>
            <input type="number" v-model.number="entry.finishOffsetDays" placeholder="Offset days" />

          <div class="calculated-finish">
            <strong>Calculated Finish Date => &nbsp;</strong>
            <span>
              {{ calculateFinishDate(selectedDate, entry.finishOffsetMonths, entry.finishOffsetDays) || 'N/A' }}
            </span>
          </div>
          <button type="button" class="remove-btn small" @click="removeBusyLine(idx)">Remove</button>
        </div>
        <button type="button" class="add-btn" @click="addBusyLine">+ Add Busy Line Entry</button>
      </div>

      <!-- 4) Additional Parameters (Always Visible) -->
      <div class="card">
        <h2>Additional Parameters</h2>
        <label for="monthsCountSelect"><strong>Months Count:</strong></label>
        <select id="monthsCountSelect" v-model.number="monthsCount">
          <option :value="12">12 months</option>
          <option :value="15">15 months</option>
        </select>
        <!-- Add Date Picker -->
        <label for="datePicker"><strong>Select a Date:</strong></label>
        <datepicker id="datePicker" v-model="selectedDate" :format="customFormat"></datepicker>
      </div>

      <!-- Submit Button -->
      <div class="submit-section">
        <button type="submit" class="submit-btn">Generate Plan</button>
      </div>
    </form>



    <!-- Error & Results -->
    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="planner" class="results">
      <h2>Planner Raw Data</h2>
      <pre class="json-box">{{ JSON.stringify(planner, null, 2) }}</pre>
    </div>


    <!-- Show the demand reduction (differences) -->
    <div v-if="Initial_Inventory_Amount" class="results">
      <h2>Initial Inventory Amount</h2>
      <pre class="json-box">{{ JSON.stringify(Initial_Inventory_Amount, null, 2) }}</pre>
    </div>

    <!-- Show the demand reduction (differences) -->
    <div v-if="demand_reduction" class="results">
      <h2>Demand Reductions</h2>
      <pre class="json-box">{{ JSON.stringify(demand_reduction, null, 2) }}</pre>
    </div>

    <div v-if="feasible_capacity" class="results">
      <h2>Plan made by demands below:</h2>
      <pre class="json-box">{{ JSON.stringify(feasible_capacity, null, 2) }}</pre>
    </div>

    <div v-if="timeline_chart" class="chart-container">
      <h2>Timeline Chart</h2>
      <img :src="'data:image/png;base64,' + timeline_chart" alt="Timeline Chart" />
    </div>
  </div>
</template>


<script>
import axios from "axios";
import Datepicker from 'vue3-datepicker';

export default {
  name: "FullPlanScheduler",
  components: {
    Datepicker
  },
  data() {
    return {
      selectedSection: "productsDoses", // Options: 'productsDoses', 'inventoryExpiration', 'currentStock'
      selectedProductIndex: 0,
      products: [
        {
          name: "Altebrel",
          doses: [
            {
              name: "25",
              exportMinStocks: Array(16).fill(0), // default values for export stock
              salesMinStocks: Array(16).fill(0),  // default values for sales stock
            },
            {
              name: "50",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
          ],
        },
        {
          name: "AryoTrust",
          doses: [
            {
              name: "150",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
            {
              name: "440",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
          ],
        },
        {
          name: "Zytux",
          doses: [
            {
              name: "100",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
            {
              name: "500",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
          ],
        },
        {
          name: "Stivant",
          doses: [
            {
              name: "100",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
            {
              name: "400",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
          ],
        },
        {
          name: "Arylia",
          doses: [
            {
              name: "60",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
            {
              name: "120",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
          ],
        },
        {
          name: "AryoSeven_RC ( NOT AVAILABLE YET )",
          doses: [
            {
              name: "1.2",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
            {
              name: "2.4",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
            {
              name: "4.8",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
          ],
        },
        {
          name: "AryoSeven_BR",
          doses: [
            {
              name: "1.2",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
            {
              name: "2.4",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
            {
              name: "4.8",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
          ],
        },
        {
          name: "Coageight",
          doses: [
            {
              name: "500",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
            {
              name: "1000",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
            {
              name: "2000",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
          ],
        },
        {
          name: "VedAryo ( NOT AVAILABLE YET )",
          doses: [
            {
              name: "300",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
          ],
        },
        {
          name: "Temziva ( NOT AVAILABLE YET )",
          doses: [
            {
              name: "200",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
            {
              name: "400",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
          ],
        },
      ],
      commonBRs: [],
      dedicatedBRs: [],
      monthsCount: 12,
      planResult: null,
      planner: null,
      timeline_chart: null,  // new property for the timeline chart image
      error: null,
      selectedDate: null,
      customFormat: 'dd/MM/yyyy',
      inventoryData: [],
      currentStocks: [],
      // New Busy Lines data:
      busyLines: [],
      // Available lines loaded from the server
      availableLines: [],
    };
  },
  computed: {
    currentProduct() {
      return this.products[this.selectedProductIndex] || null;
    },
    // Build a list of product-dose options using only those product doses that have nonzero demand,
    // or fallback to all product-dose pairs if none have nonzero demand.
    demandedProductOptions() {
      const options = [];
      this.products.forEach((product) => {
        if (product.name && product.doses) {
          product.doses.forEach((dose) => {
            if (dose.name && this.hasNonZeroDemand(dose)) {
              options.push({
                value: `${product.name}|${dose.name}`,
                label: `${product.name} - ${dose.name}`,
              });
            }
          });
        }
      });
      // Fallback: if options is empty, list all product-dose pairs.
      if (options.length === 0) {
        this.products.forEach((product) => {
          if (product.name && product.doses) {
            product.doses.forEach((dose) => {
              if (dose.name) {
                options.push({
                  value: `${product.name}|${dose.name}`,
                  label: `${product.name} - ${dose.name}`,
                });
              }
            });
          }
        });
      }
      return options;
    },
  },
  methods: {
    addProduct() {
      const newProd = {
        name: "",
        doses: [
          {
            name: "",
            exportMinStocks: Array(16).fill(0),
            salesMinStocks: Array(16).fill(0),
          },
        ],
      };
      this.products.push(newProd);
      this.selectedProductIndex = this.products.length - 1;
    },
    removeSelectedProduct() {
      if (this.products.length === 0) return;
      this.products.splice(this.selectedProductIndex, 1);
      this.selectedProductIndex = Math.min(this.selectedProductIndex, this.products.length - 1);
    },
    addDose() {
      if (!this.currentProduct) return;
      this.currentProduct.doses.push({
        name: "",
        exportMinStocks: Array(16).fill(0),
        salesMinStocks: Array(16).fill(0),
      });
    },
    removeDose(doseIndex) {
      if (!this.currentProduct) return;
      this.currentProduct.doses.splice(doseIndex, 1);
    },

    // Method to check if a product's dose has any non-zero demand
    hasNonZeroDemand(dose) {
      return dose.exportMinStocks.some((stock) => stock !== 0) || dose.salesMinStocks.some((stock) => stock !== 0);
    },
        // Inventory & Expiration section methods
    addCurrentStock() {
      this.currentStocks.push({
        productDose: "",
        amount: 0,
        expirationOffsetMonths: 0, // User enters number of months offset
        expirationOffsetDays: 0, // User enters number of months offset
      });
    },
    removeCurrentStock(index) {
      this.currentStocks.splice(index, 1);
    },
    // Busy Lines section methods:
    addBusyLine() {
      this.busyLines.push({
        line: "",
        finishOffsetMonths: 0,
        finishOffsetDays: 0,
      });
    },
    removeBusyLine(index) {
      this.busyLines.splice(index, 1);
    },

    calculateExpiration(baseDate, offsetMonths, offsetDays) {
      if (!baseDate || isNaN(offsetMonths) || isNaN(offsetDays)) return "";
      const dateObj = new Date(baseDate);
      // Add offset months; note that setMonth() automatically handles year overflow.
      dateObj.setMonth(dateObj.getMonth() + Number(offsetMonths));
      // Then add the offset days.
      dateObj.setDate(dateObj.getDate() + Number(offsetDays));
      return dateObj.toLocaleDateString();
    },

    calculateFinishDate(baseDate, offsetMonths, offsetDays) {
      if (!baseDate || isNaN(offsetMonths) || isNaN(offsetDays)) return "";
      const dateObj = new Date(baseDate);
      dateObj.setMonth(dateObj.getMonth() + Number(offsetMonths));
      dateObj.setDate(dateObj.getDate() + Number(offsetDays));
      return dateObj.toLocaleDateString();
    },
    async submitPlan() {
      this.error = null;
      this.planResult = null;
      this.planner = null;
      this.demand_reduction = null;
      this.Initial_Inventory_Amount = null;
      this.feasible_capacity = null;
      this.timeline_chart = null;  // Reset the timeline chart image

      try {
        const minStock = {};
        const productsDict = {};
        const exportStocks = {}; // Added field for export stocks
        const salesStocks = {}; // Added field for sales stocks

        // Loop through products and filter out products with no non-zero demands
        this.products.forEach((product) => {
          if (!product.name) return;

          const dosesWithNonZeroDemands = product.doses.filter((dose) => this.hasNonZeroDemand(dose));
          if (dosesWithNonZeroDemands.length > 0) {
            minStock[product.name] = {};
            exportStocks[product.name] = {}; // Initialize exportStocks
            salesStocks[product.name] = {}; // Initialize salesStocks
            productsDict[product.name] = [];

            dosesWithNonZeroDemands.forEach((dose) => {
              productsDict[product.name].push(dose.name);
              minStock[product.name][dose.name] = {};
              exportStocks[product.name][dose.name] = {}; // Initialize export stock for dose
              salesStocks[product.name][dose.name] = {}; // Initialize sales stock for dose

              for (let month = 1; month <= this.monthsCount; month++) {
                const exportVal = dose.exportMinStocks[month] || 0;
                const salesVal = dose.salesMinStocks[month] || 0;
                minStock[product.name][dose.name][month] = exportVal + salesVal;

                // Store the monthly export and sales values
                exportStocks[product.name][dose.name][month] = exportVal;
                salesStocks[product.name][dose.name][month] = salesVal;
              }
            });
          }
        });

        const currentStocksPayload = this.currentStocks.map((entry) => ({
          productDose: entry.productDose,
          amount: entry.amount,
          Date: this.selectedDate,
          Expiration: this.calculateExpiration(this.selectedDate, entry.expirationOffsetMonths, entry.expirationOffsetDays),
        }));

        // Build busyLines payload with computed finish date.
        const busyLinesPayload = this.busyLines.map((entry) => ({
          line: entry.line,
          Date: this.selectedDate,
          Finish: this.calculateFinishDate(this.selectedDate, entry.finishOffsetMonths, entry.finishOffsetDays),
        }));

        // Build the payload
        const postData = {
          products: productsDict,
          Min_Stock: minStock,
          Export_Stocks: exportStocks, // Add export stocks to payload
          Sales_Stocks: salesStocks, // Add sales stocks to payload
          monthsCount: this.monthsCount,
          commonBRs: this.commonBRs,
          dedicatedBRs: this.dedicatedBRs,
          selectedDate: this.selectedDate,  // Add the date picker value
          currentStocks: currentStocksPayload,
          busyLines: busyLinesPayload,

        };

        // Send the filtered data to the backend
        const response = await axios.post("http://127.0.0.1:8200/api/plan/", postData);
        this.planResult = response.data.formatted_schedule;
        this.planner = response.data.planner;
        this.demand_reduction = response.data.Reduced_Demand;
        this.Initial_Inventory_Amount = response.data.Initial_Inventory_Amount;
        this.feasible_capacity = response.data.Feasible_Demand;
        this.timeline_chart = response.data.timeline_chart; // Store the timeline chart image

        if (Array.isArray(response.data.schedule)) {
          this.schedule = response.data.schedule;
        } else {
          console.warn("Expected an array in schedule, got:", response.data.schedule);
          this.schedule = [];
        }

      } catch (err) {
        console.error(err);
        this.error = err.response?.data?.error || err.message;
      }
    },
  },
  mounted() {
    axios.get("http://127.0.0.1:8200/api/lines")
      .then(response => {
        const commonLines = response.data.Common_Lines;
        const options = [];
        for (let product in commonLines) {
          commonLines[product].forEach(line => {
            options.push({
              value: `${product}|${line}`,
              label: `${product} - Line ${line}`
            });
          });
        }
        // Sort options alphabetically or by preference.
        this.availableLines = options.sort((a, b) => a.label.localeCompare(b.label));
      })
      .catch(err => {
        console.error("Error loading lines:", err);
        // Provide a fallback if needed (e.g., default to lines 0–6)
        this.availableLines = [0, 1, 2, 3, 4, 5, 6];
    });
  }
};
</script>


<style>
/* --- SAME STYLES AS BEFORE; NO CHANGES NEEDED --- */
body {
  font-family: "Poppins", sans-serif;
  background-color: #f0f4f7;
  margin: 0;
  padding: 0;
}

.datepicker {
  border: 1px solid #cccccc;
  border-radius: 5px;
  padding: 10px;
  font-size: 14px;
}

.chart-container {
  margin-top: 20px;
  text-align: center;
}
.busy-line-entry {
  margin-bottom: 15px;
  border: 1px solid #e0e0e0;
  padding: 10px;
  border-radius: 5px;
}

.current-stock-entry {
  margin-bottom: 15px;
  border: 1px solid #e0e0e0;
  padding: 10px;
  border-radius: 5px;
}
.selected-date {
  margin-bottom: 15px;
  padding: 8px;
  background-color: #f0f4f7;
  border: 1px solid #cccccc;
  border-radius: 5px;
  font-size: 14px;
}
.calculated-expiration {
  margin-top: 5px;
  font-size: 14px;
}
.busy-line-entry {
  margin-bottom: 15px;
  border: 1px solid #e0e0e0;
  padding: 10px;
  border-radius: 5px;
}
.calculated-finish {
  margin-top: 5px;
  font-size: 14px;
}

.chart-container img {
  max-width: 100%;
  border: 1px solid #ccc;
  border-radius: 10px;
}

.container {
  max-width: 1200px;
  margin: 40px auto;
  background: #ffffff;
  padding: 30px;
  border-radius: 15px;
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
}

.schedule-box {
  font-family: "Courier New", monospace;
  font-size: 14px;
  font-weight: bold;
  background-color: #f4f4f4;
  padding: 15px;
  border-radius: 8px;
  border: 1px solid #ddd;
  white-space: pre-wrap;
  overflow-x: auto;
  max-height: 400px;
  /* Adjust height as needed */
  line-height: 1.5;
}

.json-box {
  font-family: "Courier New", monospace;
  font-size: 14px;
  font-weight: bold;
  background-color: #f4f4f4;
  padding: 15px;
  border-radius: 8px;
  border: 1px solid #ddd;
  white-space: pre-wrap;
  overflow-x: auto;
  max-height: 500px;
  /* Adjust height as needed */
  line-height: 1.5;
  color: #0f0e0e;
}

.title {
  text-align: center;
  font-size: 28px;
  font-weight: bold;
  color: #333333;
  margin-bottom: 40px;
}

.card {
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 15px;
  padding: 20px;
  margin-bottom: 30px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
}

.card h2 {
  color: #007bff;
  margin-bottom: 15px;
}

.info {
  font-size: 14px;
  color: #777;
  margin-bottom: 15px;
}

.product-header,
.br-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.dose-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 8px 0;
}

h3,
h4,
h5 {
  margin: 0;
  color: #555555;
}

/* Buttons */
button {
  cursor: pointer;
  padding: 10px 20px;
  border: none;
  border-radius: 5px;
  font-size: 14px;
  transition: background-color 0.3s, color 0.3s;
  margin-top: 10px;
}

.add-btn {
  background-color: #28a745;
  color: white;
}

.add-btn:hover {
  background-color: #218838;
}

.add-btn.small {
  padding: 5px 10px;
  font-size: 12px;
  margin-top: 5px;
}

.add-btn.large {
  margin-top: 20px;
}

.remove-btn {
  background-color: #dc3545;
  color: white;
}

.remove-btn.small {
  font-size: 12px;
  padding: 5px 10px;
}

.remove-btn:hover {
  background-color: #c82333;
}

.submit-btn {
  background-color: #007bff;
  color: white;
  padding: 15px 30px;
  font-size: 16px;
}

.submit-btn:hover {
  background-color: #0056b3;
}

/* Inputs */
input[type="text"],
input[type="number"],
select {
  width: 100%;
  padding: 10px;
  margin: 8px 0 15px;
  border: 1px solid #cccccc;
  border-radius: 5px;
  transition: border-color 0.3s;
}

input:focus,
select:focus {
  border-color: #007bff;
  outline: none;
}

/* Monthly Stock Grid */
.month-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.month-entry label {
  font-size: 12px;
  color: #666666;
}

.month-entry input {
  font-size: 12px;
}

/* Additional small utility classes for the sub-selector */
.selector-panel {
  display: flex;
  flex-direction: column;
  margin-bottom: 15px;
}

.selector-panel label {
  margin-bottom: 5px;
}

.selector-buttons {
  display: flex;
  gap: 10px;
}

/* Results & Error */
.error {
  color: #dc3545;
  font-weight: bold;
  margin-top: 20px;
}

.results {
  background: #f9f9f9;
  padding: 20px;
  border-radius: 10px;
  border: 1px solid #e0e0e0;
  margin-top: 20px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
}
</style>