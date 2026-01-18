import { getDataBackEnd } from "/static/js/sisVar.js";
import { AppLoader } from '/static/js/loader.js';

getDataBackEnd();

/*****************DEBUG**********************/
import { __debugState } from '../../js/sisVar.js';

window.__DEBUG__ = {
  get state() {
    return __debugState();
  }
};

function exibir() {
  console.log(window.__DEBUG__.state);
}

document.getElementById('teste').addEventListener('click', exibir);