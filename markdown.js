/* Limited Markdown renderer for untrusted policy and model text.
 * Raw HTML is always escaped. Links and images are never made clickable. */
function renderMarkdown(value) {
  const escape = text => String(text).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const inline = text => escape(text)
    .replace(/`([^`\n]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
  const lines = String(value ?? '').replace(/\r\n?/g,'\n').split('\n');
  let output = '', paragraph = [], list = null, code = null;
  const flushParagraph = () => { if (paragraph.length) { output += '<p>'+paragraph.map(inline).join('<br>')+'</p>'; paragraph=[]; } };
  const closeList = () => { if (list) { output += '</'+list+'>'; list=null; } };
  for (const line of lines) {
    if (/^\s*```/.test(line)) {
      flushParagraph(); closeList();
      if (code === null) code=[];
      else { output += '<pre><code>'+escape(code.join('\n'))+'</code></pre>'; code=null; }
      continue;
    }
    if (code !== null) { code.push(line); continue; }
    if (!line.trim()) { flushParagraph(); closeList(); continue; }
    const heading = line.match(/^\s{0,3}(#{1,6})\s+(.+)$/);
    if (heading) { flushParagraph(); closeList(); const level=Math.min(heading[1].length+2,6); output += '<h'+level+'>'+inline(heading[2])+'</h'+level+'>'; continue; }
    const item=line.match(/^\s{0,3}([-*+]\s+|\d+[.)]\s+)(.+)$/);
    if (item) {
      flushParagraph(); const type=/^\d/.test(item[1])?'ol':'ul';
      if (list !== type) { closeList(); list=type; output+='<'+type+'>'; }
      output+='<li>'+inline(item[2])+'</li>'; continue;
    }
    closeList(); paragraph.push(line);
  }
  flushParagraph(); closeList();
  if (code !== null) output += '<pre><code>'+escape(code.join('\n'))+'</code></pre>';
  return output;
}
if (typeof module !== 'undefined' && module.exports) module.exports = {renderMarkdown};
