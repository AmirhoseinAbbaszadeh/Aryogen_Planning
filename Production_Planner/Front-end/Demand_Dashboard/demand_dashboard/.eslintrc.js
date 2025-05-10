module.exports = {
    parserOptions: {
      ecmaVersion: 2020,
      sourceType: 'module',
    },
    env: {
      browser: true,
      es2021: true,
    },
    extends: [
      'plugin:vue/vue3-recommended',
      // other extends...
    ],
    plugins: [
      'vue',
      // other plugins...
    ],
    rules: {
      // your custom rules...
    }
  };