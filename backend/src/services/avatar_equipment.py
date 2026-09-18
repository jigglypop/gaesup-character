"""Metric sockets for optional equipment on a selected saved body."""
EQUIPMENT = {'weapon': 'RightHand', 'tool': 'LeftHand', 'glasses': 'Head'}


def equipment_spec(spec):
    anchors = spec['anchors']
    height = spec['body_height_m']
    head = spec.get('measured_head_bounds_m', spec['fitting']['bounds']['body'])
    neck, crown = anchors['neck'][1], anchors['crown'][1]
    sockets = {}
    for slot, bone in EQUIPMENT.items():
        if slot == 'glasses':
            width = (head[1][0]-head[0][0])*.72
            size = [width, (crown-neck)*.16, (head[1][2]-head[0][2])*.65]
            socket = [anchors['crown'][0], head[0][1]+(head[1][1]-head[0][1])*.40, head[1][2]+.008]
            pivot = [.5, .5, 1.0]
        else:
            socket = anchors['wrist_right' if slot == 'weapon' else 'wrist_left'][:]
            size = [height*.12, height*(.42 if slot == 'weapon' else .28), height*.08]
            pivot = [.5, .2, .5]
        box = [[socket[i]-size[i]*pivot[i] for i in range(3)],
               [socket[i]+size[i]*(1-pivot[i]) for i in range(3)]]
        spec['fitting']['bounds'][slot] = box
        spec['envelopes'][slot] = [[box[0][i]-.02 for i in range(3)], [box[1][i]+.02 for i in range(3)]]
        sockets[slot] = {'bone': bone, 'position_m': socket, 'pivot_fraction': pivot, 'size_m': size}
    spec['equipment'] = sockets
    return spec
