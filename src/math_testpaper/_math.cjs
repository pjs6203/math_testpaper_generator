/* This process reads TeX from JSON and writes SVG. It never runs user code,
 * opens a browser, follows TeX URLs, or loads user-supplied TeX packages. */
const fs = require('fs');
const {mathjax} = require('mathjax-full/js/mathjax.js');
const {TeX} = require('mathjax-full/js/input/tex.js');
const {SVG} = require('mathjax-full/js/output/svg.js');
const {liteAdaptor} = require('mathjax-full/js/adaptors/liteAdaptor.js');
const {RegisterHTMLHandler} = require('mathjax-full/js/handlers/html.js');
require('mathjax-full/js/input/tex/ams/AmsConfiguration.js');
require('mathjax-full/js/input/tex/newcommand/NewcommandConfiguration.js');
if (process.argv[2] === '--version') { console.log(require('mathjax-full/package.json').version); process.exit(0); }
const adaptor = liteAdaptor();
RegisterHTMLHandler(adaptor);
const doc = mathjax.document('', {
  InputJax: new TeX({packages:['base','ams','newcommand'], maxBuffer:20000, maxMacros:2000}),
  OutputJax: new SVG({fontCache:'none'})
});
const keys = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const result = {};
for (const key of keys) {
  const svg = adaptor.outerHTML(doc.convert(key.slice(2), {display:key.startsWith('D:')}));
  if (/data-mjx-error|data-mml-node="merror"/.test(svg)) throw Error('Invalid TeX: '+key);
  result[key] = svg.slice(svg.indexOf('<svg'), svg.lastIndexOf('</svg>')+6);
}
fs.writeFileSync(process.argv[3], JSON.stringify(result));
