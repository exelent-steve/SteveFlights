// Paste into the Chrome javascript_tool on a loaded Kiwi.com results page.
// Reads each result card via Kiwi's stable data-test attributes.
//
// Each card's text looks like:
//   Outbound | 19:25 | 7h 40m | 01:05 | +1 | TLV | 1 stop · Heraklion | LPL |
//   Inbound  | 20:50 | 9h 35m | 08:25 | +1 | LPL | 1 stop · Bucharest | TLV |
//   2 | 0 | Self-transfer | ₪ 4,561 | for 2 passengers | Select
//
// Reading: "+1" = arrives next day; "N stop · City" = layover; price is the
// TOTAL for the party. Kiwi only renders ~4-8 cards (virtualized) — since the
// URL sorts by price with 1-stop+no-overnight applied, the top cards ARE the
// cheapest compliant options, which is what we want.
//
// NOTE: do NOT return location.href / the URL — the harness blocks output that
// contains query-string data. Return only the card text.

(() => {
  const cards = [...document.querySelectorAll('[data-test="ResultCardWrapper"]')];
  const out = cards.slice(0, 8).map(card => {
    const price = card.querySelector('[data-test="ResultCardPrice"]')
      ?.innerText.replace(/\s+/g, ' ').trim() || '';
    const full = card.innerText.replace(/\n+/g, ' | ').replace(/\s+/g, ' ').trim();
    return { price, detail: full.slice(0, 320) };
  });
  return JSON.stringify({ source: 'kiwi', count: cards.length, cards: out }, null, 1);
})();
