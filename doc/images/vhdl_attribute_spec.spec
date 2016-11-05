stack(
 line('attribute', '/(attribute) identifier', 'of'),
 line(choice(toploop('/entity_designator', ','), 'others', 'all'), ':'),
 line('/entity_class', 'is', '/expression', ';')
)

#url_map = {
#  'entity_class': 'http://www.google.com',
#  'attribute identifier': 'http://www.google.com'
#}
