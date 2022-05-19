const item = document.getElementById("item");

// Update part names as item type changes
function updateNames(templateData) {

    const templates = JSON.parse(templateData);

    const itemSelection = document.getElementById("item");
    const colorA = document.getElementById("colorA");
    const colorB = document.getElementById("colorB");
    const colorC = document.getElementById("colorC");

    for (let i in templates.loterias) {
        if (itemSelection.value == templates.loterias[i].nombre) {
            colorA.innerHTML = templates.loterias[i].a
            colorB.innerHTML = templates.loterias[i].b

            // Change the ColorC heading to "-"
            if (templates.loterias[i].c == '') {
                colorC.innerHTML = '-';

                // Unselect all ColorC radios
                for (let i in templates.colors) {
                    if (templates.colors[i].sku <= 7) { // don't include extended colors
                        let selection = document.getElementById(`${templates.colors[i].name}c`);
                        selection.checked = false;
                    }
                }
            } else {
                colorC.innerHTML = templates.loterias[i].c
            }
        }
    }
}
updateNames(templateData); // update once
item.addEventListener('change', () => { updateNames(templateData) }, false); // add listener



// let scrollPos = document.cookie;

function storeScroll() {
    scrollPos = window.scrollY
    console.log(`settingScrollPos=${scrollPos}`);
    document.cookie = `scrollPos=${scrollPos}`;
}

function getCookie(cname) {
    // https://www.w3schools.com/js/js_cookies.asp
    console.log(`parsing document.cookie:${document.cookie}`)
    let name = cname + "=";
    let decodedCookie = decodeURIComponent(document.cookie);
    let ca = decodedCookie.split(';');
    for(let i = 0; i <ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) == ' ') {
        c = c.substring(1);
        }
        if (c.indexOf(name) == 0) {
        return c.substring(name.length, c.length);
        }
    }
    return "";
    }

function updateScroll() {
    let scrollPos = getCookie('scrollPos')
    if (scrollPos) {
        window.scroll(0,scrollPos);
    }
}

updateScroll();
addEventListener('beforeunload', function () { storeScroll(); }, false);
