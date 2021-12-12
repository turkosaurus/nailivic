// SKU copy button
function copy() {
    var copyText = document.querySelector("#sku");
    copyText.select();
    document.execCommand("copy");
    // alert("SKU copied to clipboard: " + copyText.value);
    }

document.querySelector("#copy").addEventListener("click", copy);


// Clear Form (/items)
// https://stackoverflow.com/questions/6028576/how-to-clear-a-form
function resetForm(form) {
// clearing inputs
    var inputs = form.getElementsByTagName('input');
    for (var i = 0; i<inputs.length; i++) {
        switch (inputs[i].type) {
            // case 'hidden':
            case 'text':
                inputs[i].value = '';
                break;
            case 'radio':
            case 'checkbox':
                inputs[i].checked = false;   
        }
    }

    // clearing selects
    var selects = form.getElementsByTagName('select');
    for (var i = 0; i<selects.length; i++)
        selects[i].selectedIndex = 0;

    // clearing textarea
    var text = form.getElementsByTagName('textarea');
    for (var i = 0; i<text.length; i++)
        text[i].innerHTML= '';

    return false;
}

// enable syntax highlighting
// https://codepen.io/niklass/pen/MXzJBQ
hljs.initHighlightingOnLoad()