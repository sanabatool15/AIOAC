import postcss from "postcss";
import tw from "@tailwindcss/postcss";
import fs from "fs";
const css = fs.readFileSync("app/globals.css","utf8").replace('@import "tailwindcss";','@import "tailwindcss" source(none);\n@source "/tmp/tw/t.html";');
const r = await postcss([tw()]).process(css,{from:"app/globals.css"});
const out=r.css; for (const k of ["grad-card","grad-brand","shadow-card","shadow-btn-primary","brand-track","money-line"]) { const i=out.indexOf("."+k); console.log(k, i<0?"MISSING":out.slice(i,i+160).replace(/\n/g," ")); }
