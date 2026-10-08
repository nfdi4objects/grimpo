const { createApp } = Vue

const fetchJSON = async url => fetch(url)
  .then(res => res.ok ? res.json() : null)

const app = createApp({
  data: () => ({
    openapi: null,
    // status
    title: "",
    connected: false,
    frontend: "",
    base: "",
    mappings: 0,
    collections: 0,
    terminologies: 0,
    stage: undefined,

    // ...
    sparql: null,
    tab: "collection",
    sparqlStatus: "connecting...",
    sparqlError: false,
    dir: null,
    files: [],    
    error: false,
    message: null,
  }),
  watch: {
    tab(value) {
      if (value === "data") {
        fetchJSON("data/").then(files => this.files = files)
      }
    },
  },
  created() {
    fetchJSON("openapi.json").then(openapi => this.openapi = openapi)
    this.updateStatus()  
  },
  methods: {
    async updateStatus() {
      fetchJSON("status.json").then(status => {
        for (let key in status) { // TODO: don't use all keys
          this[key] = status[key]
        }
        document.getElementsByTagName("title")[0].textContent = this.title
        if (this.connected) {
          const endpoint = this.sparql || "sparql"
          fetch(`${endpoint}?query=SELECT%20*%20%7B%20BIND(1%20as%20%3Fx)%20%7D`).then(() => {
            this.sparqlStatus = "SPARQL backenend is connected and reachable"
            // TODO: show Yasgui
          }).catch(() => {
            this.sparqlStatus = "SPARQL backend is connected but not accessible from outside!"
          })
        } else {
          this.sparqlStatus = "API is not connected to SPARQL endpoint!"
          this.sparqlError = true
        }
      })
    },
    async submit(url, options) {
      this.error = false
      this.message = "loading..."

      const res = await fetch(url, options)
        .catch(e => ({ statusText: `${e}` }))
      if (res.ok) {
        this.message = res.statusText
      } else {      
        let error = res.statusText || "ERROR"
        try {
          error = (await res.json()).message 
          } catch { }  // eslint-disable-line
        this.error = error
      }
      this.updateStatus()
    },
  },
})

// A modal dialog
app.component("modal", {
  template: "#Modal",
  props: ["opened"],
  emits: ["close"], 
})
 
// Select from a list of items
app.component("selector", {
  template: "#Selector",
  props: ["prefix"],
  emits: ["select"], 
  data: () => ({ list: [] }),
  created() {
    fetchJSON(this.prefix).then(data => this.list = data)
  },
})

function expandSchema(schema, remove=[]) {
  const { $defs } = schema

  const expand = properties => {
    for (let field in properties) {
      const prop = properties[field]
      if (properties[field]["x-derived"] || remove.includes(field)) {
        delete properties[field]
      } else {
        if (properties[field].items) {
          expand(properties[field].items.properties)
        } else {
          if (prop.$ref) {
            Object.assign(prop, $defs[ prop.$ref.split("/").pop() ])
            delete prop.$ref
          }
        }
      }
    }
  }

  expand(schema.properties)

  return schema
}


// Form to modify item metadata with save button
app.component("editor", {
  template: "#Editor",
  props: ["prefix", "id"],
  emits: ["close", "saved"],
  data: () => ({
    schema: {},
    item: {},
    missing: false,
  }),
  async created() {
    fetchJSON(`${this.prefix}/schema.json`)
      .then(data => this.schema = expandSchema(data))
    if (this.id) {
      fetch(`${this.prefix}/${this.id}`).then(async res => {
        if (res.ok) {
          this.item = await res.json()
        } else {
          this.missing = true
        }
      })
    }
  },
  computed: {
    method() {
      return this.id ? "PUT" : "POST"
    },
  },
  methods: {
    async save() {
      this.$emit("close")
      const url = this.id ? `${this.prefix}/${this.id}` : this.prefix
      this.$root.submit(url, {
        method: this.method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(this.item),
      })
    },
  },
})
 
// Form to edit an item
app.component("EditorForm", {
  template: "#EditorForm",
  props: ["schema", "item"],
})

// A list of API endpoints
app.component("endpoints", {
  template: "#Endpoints",
  props: ["openapi", "prefix"],
  data: () => ({
    id: 0,
    modal: null,
    item: null,
  }),
  computed: {
    hasId() {
      return Object.keys(this.selectedPaths).find(p => p.includes("{id}"))
    },
    selectedPaths() {
      const paths = this.openapi?.paths || {}
      const selected = Object.keys(paths).filter(p => p.startsWith(`/${this.prefix}`))
      return Object.fromEntries(selected.map(p => [p, paths[p]]))
    },
  },
  watch: {
    id: {
      async handler() {
        this.item = this.hasId && this.id
          ? await fetchJSON(`${this.prefix}/${this.id}`) : null
      },
      immediate: true,
    },
  },
  methods: {
    async select(id) {
      this.id = id 
      this.modal = null
    },
  },
})

// A documented API endpoint, usable via user interface
app.component("endpoint", {
  template: "#Endpoint",
  props: ["method", "path", "operation", "id"],
  emits: ["execute"],
  data: () => ({ from: "", file: null }),
  computed: {
    disabled() {
      return this.path.includes("{id}") && !(this.id>0)
    },
    help() {
      return `https://github.com/nfdi4objects/grimpo#${this.method}-${this.path.replaceAll(/[^a-z]/g,"")}` 
    },
  },
  methods: {
    selectFile(event) {
      this.file = event.target.files[0] 
    },
    async click() {
      let url = this.path.replace("{id}",this.id).replace(/^[/]/,"")
      if (this.method == "get") {
        window.location.href = url
        return
      }

      if (this.operation.parameters) {  // there is only one possible parameter
        url += `?from=${encodeURI(this.from)}`
      }
      
      if (this.operation.requestBody && !this.from) { // file upload        
        if (this.file) {
          const reader = new FileReader()
          reader.onload = async e => await this.$root.submit(url, {
            method: this.method,
            headers: { "Content-Type": "application/json" },
            body: e.target.result,
          })
          reader.readAsText(this.file)
        } else {
          this.$root["error"] = "Please select a file!"
        }
        return
      }

      return this.$root.submit(url, { method: this.method })
    },
  },
})

// A list of files for download
app.component("files", {
  template: "#Files",
  props: ["path"],
  data: () => ({ files: [] }),
  watch: {
    path: {
      async handler(url) {
        this.files = await fetchJSON(url)
      },
      immediate: true,
    },
  },
})

app.component("sparql-editor", {
  template: "<div ref='editor'></div>",
  props: ["endpoint"],
  data: () => ({ yasgui: null }),
  mounted() {
    if (window.Yasgui) {
      this.yasgui = new window.Yasgui(this.$refs.editor, { requestConfig: { endpoint: this.endpoint }})
    }
  },
})

app.mount("#app")
