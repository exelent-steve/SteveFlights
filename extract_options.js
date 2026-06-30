// Paste into the Chrome javascript_tool on a loaded Skyscanner results page.
// Waits for results, then returns each "Flight option" with full times,
// stops, layover airports and duration — the detail needed to judge a trip.
//
// Self-transfer + overnight detection is done downstream from the text
// ("one day later" => crosses midnight; "Self-transfer" => virtual interline).

(async () => {
  await new Promise(r => setTimeout(r, 5500));
  const text = document.body.innerText;
  const parts = text.split(/(?=Flight option \d+:)/);
  const options = parts
    .filter(p => p.startsWith('Flight option '))
    .map(o => {
      const clean = o.replace(/\n+/g, ' ');
      const end = clean.indexOf('Prices include taxes');
      return (end > 0 ? clean.slice(0, end) : clean.slice(0, 550)).trim();
    });
  return JSON.stringify({
    title: document.title.slice(0, 50),
    isSelfTransfer: text.includes('Self-transfer'),
    count: options.length,
    options: options.slice(0, 8),
  });
})();
