import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { test } from "node:test"
import { JSDOM } from "jsdom"
import vm from "node:vm"

test("Vue application starts and executes", async () => {
  const html = await readFile("index.html")
  const vue = await readFile("vue.global.js")
  const ui = await readFile("ui.js")

  const dom = new JSDOM(html, {
    url: "http://localhost/",
    runScripts: "outside-only",
  })
  const { window } = dom

  // Mock HTTP responses
  window.fetch = async url => {
    let data = []
    if (url == "status.json") {
      data = {
        title: "Test",
        connected: false,
        paths: {},
      }
    } else if (url == "data/") {
      data = []
    } else if (url == "openapi.json") {
      data = {}
    } else {
      console.error(`UNHANDLED FETCH ${url}`)
    }

    return { json: async () => data, ok: 1 }
  }

  // Load Vue runtime and UI application
  const context = vm.createContext(window)
  vm.runInContext(vue.toString(), context, { filename: "vue.global.js" })
  vm.runInContext(ui.toString(), context, { filename: "ui.js" })

  // Await initialization
  await new Promise(resolve => setImmediate(resolve))

  // Actual tests
  assert.equal(window.document.querySelector("#app").id, "app")
  assert.equal(window.document.title, "Test")    
})
