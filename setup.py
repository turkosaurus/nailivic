import csv

loterias = {
    'La Dama': ['Frida', 'Frida Flowers', 'Frida Backs'],
    'La Sirena': ['Mermaid Body', 'Mermaid Hair', 'Mermaid Tail', 'Mermaid Backs'],
    'La Mano': ['Hand', 'Hand Swirls', 'Hand Backs'],
    'La Bota': ['Boot', 'Boot Swirls', 'Boot Flames', 'Boot Backs'],
    'El Corazon': ['Heart', 'Heart Swirls', 'Heart Backs'],
    'El Musico': ['Guitar', 'Guitar Hands', 'Guitar Backs'],
    'La Estrella': ['Star', 'Star Swirls', 'Star Backs'],
    'El Pulpo': ['Octopus', 'Octopus Swirls', 'Octopus Tentacles', 'Octopus Backs'],
    'La Rosa': ['Rose', 'Rose Swirls', 'Rose Leaves', 'Rose Backs'],
    'La Calavera': ['Skull', 'Skull Flames', 'Skull Swirls', 'Skull Backs'],
    'El Poder': ['Fist', 'Fist Swirls', 'Fist Wrist', 'Fist Backs']
}

with open('loterias.csv', 'w', newline='') as csvfile:
    loteria = csv.writer(csvfile, delimiter=',', quotechar='|')
    print(loterias)
    for item in loterias:
        tmp = []
        tmp.append(item)
        for piece in loterias[item]:
            tmp.append(piece)
        loteria.writerow(tmp)
