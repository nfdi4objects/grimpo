const { createApp } = Vue

const fetchJSON = async url => fetch(url).then(res => res.json())

const app = createApp({
  data: () => ({
    // status
    title: "",
    paths: {},
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
  },
})

// A list of API endpoints
app.component("endpoints", {
  template: "#Endpoints",
  props: ["paths", "prefix"],
  data: () => ({ id: 0 }),
  computed: {
    hasId() {
      return Object.keys(this.selectedPaths).find(p => p.includes("{id}"))
    },
    selectedPaths() {
      const selected = Object.keys(this.paths).filter(p => p.startsWith(`/${this.prefix}`))
      return Object.fromEntries(selected.map(p => [p, this.paths[p]]))
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
      if (this.operation.parameters) {  // there is only one possible parameter
        url += `?from=${encodeURI(this.from)}`
      }
      if (this.method == "get") {
        window.location.href = url
        return
      }
      this.$root["error"] = false
      this.$root["message"] = "loading..."
      
      const submit = async options => {
        const res = await fetch(url, { ...options, method: this.method })
          .catch(e => ({ statusText: `${e}` }))
        if (res.ok) {
          this.$root["message"] = res.statusText
        } else {      
          let error = res.statusText || "ERROR"
          try {
            error = (await res.json()).message 
          } catch { }  // eslint-disable-line
          this.$root["error"] = error
        }
        this.$root.updateStatus()
      }

      if (this.operation.requestBody) { // file upload        
        if (this.file) {
          const reader = new FileReader()
          reader.onload = async e => await submit({
            method: this.method,
            headers: { "Content-Type": "application/json" },
            body: e.target.result,
          })
          reader.readAsText(this.file)
        } else {
          this.$root["error"] = "Please select a file!"
        }
      } else {
        return submit({})
      }
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

app.mount("#app")
