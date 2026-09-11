const idValue = { terminology: "", collection: "", mappings: "" }

const updateId = (cls, value) => {
  idValue[cls] = value
  for (let e of document.getElementsByClassName(cls)) {
    e.parentNode.getElementsByTagName("a")[0].className = value ? "enabled" : "disabled"
    e.value = value
  }
}

const clearMessages = () => {
  for (let e of document.getElementsByClassName("msg")) {
    e.classList.remove("error")
    e.textContent = ""
  }
}

const errorMessage = (id, error) => {
  const elem = document.getElementById(id)
  elem.classList.add("error")
  elem.textContent = error
}

const visit = (e, url) => {
  if (e?.className == "disabled") return true
  window.location.href = url.replace(":id", idValue[url.split("/")[0]])
}

const request = async (e, url, method) => {
  if (e?.className == "disabled") return true

  const id = method.toLowerCase() + "-" + url.replaceAll(/\?.*|[^a-z]/g,"")
  url = url.replace(":id", idValue[url.split("/")[0]])
  const options = { method }

  const submit = async () => {
    document.getElementById(id).textContent = "...loading..."
    const res = await fetch(url, options).catch(e => ({ statusText: `${e}` }))
    if (res.ok) {
      document.getElementById(id).textContent = res.statusText
    } else {      
      var error = res.statusText || "ERROR"
      try { error = (await res.json()).error } catch {}
      errorMessage(id, error)
    }
    status()
  }

  clearMessages()
  
  const upload = document.getElementById(`${id}-file`)
  if (upload) {
    const file = upload.files[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = async e => {
        options.headers = { 'Content-Type': 'application/json' }
        options.body = e.target.result
        await submit()
      }
      reader.readAsText(file)
    } else {
      errorMessage(id, "Please select a file!")
      return
    }
  } else {
    await submit()
  }
}

const getValue = id => document.getElementById(id).value

const registerTerminology  = e => request(e,`terminology/:id`, "PUT")
const replaceTerminologies = e => request(e,`terminology/`, "PUT")
const deleteTerminology    = e => request(e,`terminology/:id`, "DELETE")
const receiveTerminology   = e => request(e,`terminology/:id/receive?from=${getValue('receiveTerminology')}`, "POST")
const loadTerminology      = e => request(e,`terminology/:id/load`, "POST")
const removeTerminology    = e => request(e,`terminology/:id/remove`, "POST")

const registerCollection = e => request(e,`collection/`, "POST")
const replaceCollections = e => request(e,`collection/`, "PUT")
const updateCollection   = e => request(e,`collection/:id`, "PUT")
const deleteCollection   = e => request(e,`collection/:id`, "DELETE")
const receiveCollection  = e => request(e,`collection/:id/receive?from=${getValue('receiveCollection')}`, "POST", "receiveCollection")
const loadCollection     = e => request(e,`collection/:id/load`, "POST")
const removeCollection   = e => request(e,`collection/:id/remove`, "POST")

const registerMappings   = e => request(e,`mappings/`, "POST")
const replaceMappings    = e => request(e,`mappings/`, "PUT")
const updateMappings     = e => request(e,`mappings/:id`, "PUT")
const deleteMappings     = e => request(e,`mappings/:id`, "DELETE")
const appendMappings     = e => request(e,`mappings/:id/append`, "POST")
const detachMappings     = e => request(e,`mappings/:id/detach`, "POST")
const receiveMappings    = e => request(e,`mappings/:id/receive?from=${getValue('receiveMappings')}`, "POST", "receiveMappings")
const loadMappings       = e => request(e,`mappings/:id/load`, "POST")
const removeMappings     = e => request(e,`mappings/:id/remove`, "POST")

function status() {
  const sparqlStatus = document.getElementById('sparql-status')

  fetch(`status.json`).then(res => res.json()).then(s => {

    // Vue clone in two lines!
    document.querySelectorAll('[v-text]').forEach(e => e.textContent = s[e.getAttribute("v-text")])
    document.querySelectorAll('a[\\:href]').forEach(a => a.href = s[a.getAttribute(":href")])

    if (s.connected) {
      document.getElementById('backend').className = ''

      for (let key of ["terminologies", "mappings", "collections"]) {
        document.getElementById(key).textContent = ` (${s[key]})`
      }

      if (sparqlStatus) {
        sparqlStatus.className = ""
        const yasgui = document.getElementById("yasgui")
        const endpoint = s.sparql || `sparql`
        fetch(`${endpoint}?query=SELECT%20*%20%7B%20BIND(1%20as%20%3Fx)%20%7D`).then(() => {
          sparqlStatus.innerHTML = "SPARQL backenend is connected and reachable";
          //new Yasgui(yasgui, { requestConfig: { endpoint }});
        })
        sparqlStatus.innerHTML = "SPARQL backend is connected but not accessible from outside!"
      }
      return
    } else {
      if (sparqlStatus) {
        sparqlStatus.className = "error"
        sparqlStatus.innerHTML = "SPARQL backend is not connected!"
      }
      document.getElementById('backend').className = 'error'
    }
    if (sparqlStatus) {
      sparqlStatus.className = "error"
    }
  })
}

function selectTab(id) {
  const toggle = document.getElementById(`tab-${id}-toggle`) || document.getElementById(`tab-collection-toggle`)
  if (toggle) {
    toggle.checked = true
    const filesDiv = document.getElementById(`${id}-files`)
    if (filesDiv) {
        const url = filesDiv.attributes["data-path"].value
        fetch(url).then(res => res.json()).then(files => {
          if (files.length) {
            const list = document.createElement("ul")
            for (const file of files) {
              const li = document.createElement("li")
              const a = document.createElement("a")
              a.href = `${url}${file.name}`
              a.textContent = file.name
              li.appendChild(a)
              list.appendChild(li)
            }              
            filesDiv.replaceChildren(list)
          } else {
            filesDiv.innerHTML = "The directory is empty."
          }
        })
      }
  }
}

window.addEventListener('hashchange', () => selectTab(window.location.hash?.substr(1)))

window.onload = () => {
  selectTab(window.location.hash?.substr(1))

  document.querySelectorAll("[name='tabs-toggle']")
    .forEach(radio => radio.addEventListener("change", e => {
      const path = window.location.pathname
      const id = e.target.id.split("-")[1]
      selectTab(id)
      history.replaceState(null, null, `#${id}`)
    }))

  for (let cls in idValue) {
    const nodes = document.getElementsByClassName(cls)
    if (nodes.length) {
      for (let elem of nodes) {
        elem.addEventListener("input", ({target: {value}}) => {        
          updateId(cls, value)
          return true
        })
      }
      updateId(cls, nodes[0].value)
    }
  }
  status()
}
