stack(
 line('attribute', '/(attribute) identifier', 'of'),
 line(choice(toploop('/entity_designator', ','), 'others', 'all'), ':'),
 line('/entity_class', 'is', '/expression', ';')
)

url_map = {
  'entity_class': 'https://www.google.com/#q=vhdl+entity+class',
  '(attribute) identifier': 'http://en.wikipedia.com/wiki/VHDL'
}
