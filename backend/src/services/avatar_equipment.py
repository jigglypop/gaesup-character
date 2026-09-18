"""Additive Maple SD equipment contract; old eight-layer designs remain readable."""
from typing import Literal

ImageSlot = Literal['body', 'hair', 'head', 'face', 'hairBack', 'hairFront', 'hat', 'top', 'bottom', 'shoes',
                    'weapon', 'shield', 'back', 'faceAccessory', 'neckAccessory']
EQUIPMENT = {
    'weapon': {'label': '무기', 'slot': 'hand', 'bone': 'handR', 'size': .9,
               'anchor': [.5, .15, .5], 'placement': [50, 220, 100, 250],
               'description': 'one Maple-style fantasy sword or staff, upright with its grip centered at 15 percent of the full height from the bottom; complete handle and blade, no hand or character'},
    'shield': {'label': '방패', 'slot': 'offhand', 'bone': 'handL', 'size': .5,
               'anchor': [.5, .5, .1], 'placement': [340, 300, 130, 140],
               'description': 'one small fantasy shield, front toward camera, complete back handle centered behind the shield; no arm or character'},
    'back': {'label': '등 장비', 'slot': 'back', 'bone': 'upperChest', 'size': .65,
             'anchor': [.5, .8, .9], 'placement': [145, 265, 220, 170],
             'description': 'one rigid back ornament or wing ornament, front toward camera, upper-center attachment against the back; no body or character'},
    'faceAccessory': {'label': '얼굴 장식', 'slot': 'faceAccessory', 'bone': 'head', 'size': .55,
                      'anchor': [.5, .5, .5], 'placement': [155, 145, 200, 80],
                      'description': 'one pair of fantasy glasses or face ornament; complete rims and temples, no face or hair'},
    'neckAccessory': {'label': '목 장식', 'slot': 'neckAccessory', 'bone': 'neck', 'size': .23,
                      'anchor': [.5, .9, .5], 'placement': [220, 275, 75, 65],
                      'description': 'one necklace with a complete chain and pendant, front toward camera; no neck, torso or character'},
}


def equipment_layer(slot, order):
    item = EQUIPMENT[slot]
    return {'slot': slot, 'label': item['label'], 'asset': None, 'crop': [0, 0, 1, 1],
            'placement': item['placement'][:], 'visible': True, 'opacity': 1., 'order': order,
            'background': 'border-gray', 'status': 'needs_image', 'description': ''}
