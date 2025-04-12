<template>
  <div class="container">
    <h1 class="title">Full Production Planning Scheduler (Dynamic Products & Doses)</h1>

    <form @submit.prevent="submitPlan">

      <!-- SECTION SELECTOR -->
      <div class="card">
        <label for="sectionSelect"><strong>Select Section:</strong></label>
        <select id="sectionSelect" v-model="selectedSection">
          <option value="productsDoses">Products & Doses</option>
          <option value="commonBRs">Common BRs (Shared)</option>
          <option value="dedicatedBRs">Dedicated BRs</option>
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
              <button type="button" class="remove-btn small" :disabled="products.length === 0"
                @click="removeSelectedProduct">
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

      <!-- 2) COMMON BRs (Shared) -->
      <div v-if="selectedSection === 'commonBRs'">
        <div class="card">
          <h2>Common Bio Reactors (Shared)</h2>
          <p class="info">
            Each Common BR automatically has fields for every Product & Dose the user creates.
          </p>

          <div v-for="(cbr, cIndex) in commonBRs" :key="cIndex" class="common-br-entry">
            <div class="br-header">
              <h3>{{ cbr.BR_Name || "Common BR" }}</h3>
              <button type="button" class="remove-btn" @click="removeCommonBR(cIndex)">Remove</button>
            </div>

            <label>BR Name:</label>
            <input type="text" v-model="cbr.BR_Name" placeholder="e.g. BR_2000-1" />

            <!-- For each product in cbr.products, for each dose in cbr.products[productName] -->
            <div v-for="(prodObj, productName) in cbr.products" :key="productName" class="cbr-product-entry">
              <h4>Product: {{ productName }}</h4>
              <div v-for="(doseObj, doseName) in prodObj" :key="doseName" class="cbr-dose-entry">
                <h5>Dose: {{ doseName }}</h5>
                <label>Production Days:</label>
                <input type="number" v-model.number="doseObj.productionDays" placeholder="e.g. 79" />
                <label>Stocks Produced:</label>
                <input type="number" v-model.number="doseObj.stocks" placeholder="e.g. 64000" />
              </div>
            </div>
          </div>

          <button type="button" class="add-btn large" @click="addCommonBR">+ Add Common BR</button>
        </div>
      </div>

      <!-- 3) DEDICATED BRs (Single Product) -->
      <div v-if="selectedSection === 'dedicatedBRs'">
        <div class="card">
          <h2>Dedicated Bio Reactors</h2>
          <p class="info">
            Each dedicated BR is bound to exactly one product, but can produce multiple doses if you wish.
          </p>

          <div v-for="(dbr, dIndex) in dedicatedBRs" :key="dIndex" class="dedicated-br-entry">
            <div class="br-header">
              <h3>{{ dbr.BR_Name || "Dedicated BR" }}</h3>
              <button type="button" class="remove-btn" @click="removeDedicatedBR(dIndex)">Remove</button>
            </div>

            <label>BR Name:</label>
            <input type="text" v-model="dbr.BR_Name" placeholder="e.g. BR_E_1250" />

            <label>Dedicated Product:</label>
            <select v-model="dbr.productName">
              <option v-for="(product, pIndex) in products" :key="pIndex" :value="product.name">
                {{ product.name }}
              </option>
            </select>

            <label>Production Days:</label>
            <input type="number" v-model.number="dbr.productionDays" placeholder="e.g. 94" />

            <div class="dedicated-dose-list">
              <p>Define doses for this BR (if needed):</p>
              <div v-for="(doseEntry, dx) in dbr.doses" :key="dx" class="dedicated-dose-entry">
                <label>Dose Name:</label>
                <input type="text" v-model="doseEntry.name" placeholder="e.g. a" />
                <label>Stocks Produced:</label>
                <input type="number" v-model.number="doseEntry.stocks" placeholder="e.g. 40000" />
                <button type="button" class="remove-btn small" @click="removeDedicatedDose(dbr, dx)">Remove</button>
              </div>
              <button type="button" class="add-btn small" @click="addDedicatedDose(dbr)">+ Add Dose</button>
            </div>
          </div>

          <button type="button" class="add-btn large" @click="addDedicatedBR">+ Add Dedicated BR</button>
        </div>
      </div>

      <!-- 4) Additional Parameters (Always Visible) -->
      <div class="card">
        <h2>Additional Parameters</h2>
        <label>Start Year:</label>
        <input type="number" v-model.number="startYear" placeholder="Enter Start Year" />

        <label>Months Count:</label>
        <input type="number" v-model.number="monthsCount" placeholder="Enter Months Count" />
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
    <div v-if="planResult" class="results">
      <h2>Schedule Results</h2>
      <pre class="schedule-box">
        <span v-for="(line, i) in planResult" :key="i">
          {{ line }}
        </span>
      </pre>
    </div>
    <div v-if="timeline_chart" class="chart-container">
      <h2>Timeline Chart</h2>
      <img :src="'data:image/png;base64,' + timeline_chart" alt="Timeline Chart" />
    </div>
  </div>
</template>

<script>
import axios from "axios";

export default {
  name: "FullPlanScheduler",
  data() {
    return {
      selectedSection: "productsDoses", // 'productsDoses' | 'commonBRs' | 'dedicatedBRs'
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
          ],
        },
        {
          name: "Artenix",
          doses: [
            {
              name: "120",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            }
          ],
        },
        {
          name: "AryoSeven_RC",
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
          name: "VedAryo",
          doses: [
            {
              name: "300",
              exportMinStocks: Array(16).fill(0),
              salesMinStocks: Array(16).fill(0),
            },
          ],
        },
        {
          name: "Temziva",
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
      startYear: null,
      monthsCount: null,
      planResult: null,
      planner: null,
      timeline_chart: null,  // new property for the timeline chart image
      error: null,
    };
  },
  computed: {
    currentProduct() {
      return this.products[this.selectedProductIndex] || null;
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

    async submitPlan() {
      this.error = null;
      this.planResult = null;
      this.planner = null;
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

              for (let month = 1; month <= 12; month++) {
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

        // Build the payload
        const postData = {
          products: productsDict,
          Min_Stock: minStock,
          Export_Stocks: exportStocks, // Add export stocks to payload
          Sales_Stocks: salesStocks, // Add sales stocks to payload
          startYear: this.startYear,
          monthsCount: this.monthsCount,
          commonBRs: this.commonBRs,
          dedicatedBRs: this.dedicatedBRs,
        };

        // Send the filtered data to the backend
        const response = await axios.post("http://127.0.0.1:8100/api/plan/", postData);
        this.planResult = response.data.formatted_schedule;
        this.planner = response.data.planner;
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

.chart-container {
  margin-top: 20px;
  text-align: center;
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