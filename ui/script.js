
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

const request = async (e, url, method) => {
  if (e?.className == "disabled") return true

  const id = method.toLowerCase() + "-" + url.replaceAll(/\?.*|[^a-z]/g,"")
  url = url.replace(":id", idValue[url.split("/")[0]])
  const options = { method }

  const submit = async args => {
    document.getElementById(id).textContent = "...loading..."
    const res = await fetch(url, args).catch(e => ({ statusText: `${e}` }))
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
      reader.onload = async e => await submit({
          method,
          headers: { 'Content-Type': 'application/json' },
          body: e.target.result,
        })
      reader.readAsText(file)
    } else {
      errorMessage(id, "Please select a file!")
      return
    }
  } else {
    await submit({ method })
  }
}


