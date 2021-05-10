import csv

# ORIGINAL LOTERIA STRUCTURE
loterias = {
    'La Dama': ['Frida', 'Frida Flowers', '', 'Frida Backs'],
    'La Sirena': ['Mermaid Body', 'Mermaid Hair', 'Mermaid Tail', 'Mermaid Backs'],
    'La Mano': ['Hand', 'Hand Swirls', '', 'Hand Backs'],
    'La Bota': ['Boot', 'Boot Swirls', 'Boot Flames', 'Boot Backs'],
    'El Corazon': ['Heart', 'Heart Swirls', '', 'Heart Backs'],
    'El Musico': ['Guitar', 'Guitar Hands', '', 'Guitar Backs'],
    'La Estrella': ['Star', 'Star Swirls', '', 'Star Backs'],
    'El Pulpo': ['Octopus', 'Octopus Swirls', 'Octopus Tentacles', 'Octopus Backs'],
    'La Rosa': ['Rose', 'Rose Swirls', 'Rose Leaves', 'Rose Backs'],
    'La Calavera': ['Skull', 'Skull Flames', 'Skull Swirls', 'Skull Backs'],
    'El Poder': ['Fist', 'Fist Swirls', 'Fist Wrist', 'Fist Backs']
}

# Write the ORIGINAL LOTERIA STRUCTURE into loterias.csv
with open('loterias.csv', 'w', newline='') as csvfile:
    print('Writing new loterias.csv')
    loteria = csv.writer(csvfile, delimiter=',', quotechar='|')
    for item in loterias:
        tmp = []
        tmp.append(item)
        for piece in loterias[item]:
            tmp.append(piece)
        loteria.writerow(tmp)