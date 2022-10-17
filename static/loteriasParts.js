const part = document.getElementById("part");

// Update part names as item type changes (for /items)
function updateNames(templateData) {

    const templates = JSON.parse(templateData);

    console.log(templates)
    console.log(part)


    const partSelection = document.getElementById("part");
    const colorA = document.getElementById("colorA");
    const colorB = document.getElementById("colorB");
    const colorC = document.getElementById("colorC");

    const colorAlabel = document.getElementById("colorAlabel");
    const colorBlabel = document.getElementById("colorBlabel");
    const colorClabel = document.getElementById("colorClabel");

    for (let i in templates.loterias) {
        if (partSelection.value == templates.loterias[i].nombre) {
            colorA.value = templates.loterias[i].a
            colorB.value = templates.loterias[i].b
            colorC.value = templates.loterias[i].c

            colorAlabel.innerHTML = templates.loterias[i].a
            colorBlabel.innerHTML = templates.loterias[i].b
            colorClabel.innerHTML = templates.loterias[i].c

            // Change the ColorC heading to "-"
            if (templates.loterias[i].c == '') {
                colorC.value = '';
                colorClabel.innerHTML = '-';

            } else {
                colorC.innerHTML = templates.loterias[i].c
            }
        }
    }
}
updateNames(templateData); // update once
part.addEventListener('change', () => { updateNames(templateData) }, false); // add listener


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
