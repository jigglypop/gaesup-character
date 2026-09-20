"""Separate adjacent sheet views in original pixel coordinates, without rescaling."""
from collections import deque
from PIL import Image


def _seam(alpha, width, height, anchor, radius):
    low, high = max(1, anchor-radius), min(width-1, anchor+radius)
    candidates = list(range(low, high+1))
    previous = [0.0] * len(candidates)
    parents = []
    for y in range(height):
        costs, row = [], []
        for i, x in enumerate(candidates):
            start, stop = max(0, i-1), min(len(candidates), i+2)
            parent = min(range(start, stop), key=lambda j: previous[j]+abs(i-j)*.15)
            # Transparent gaps are preferable to straight cuts through strands.
            opacity = max(alpha[y*width+x-1], alpha[y*width+x]) / 255
            costs.append(previous[parent] + opacity*20 + abs(x-anchor)*.08)
            row.append(parent)
        previous = costs
        parents.append(row)
    index = min(range(len(previous)), key=previous.__getitem__)
    result = [0] * height
    for y in range(height-1, -1, -1):
        result[y] = candidates[index]
        index = parents[y][index]
    return result


def _trim_fragments(tile):
    alpha = bytearray(tile.getchannel('A').tobytes())
    width, height = tile.size
    visited = bytearray(width*height)
    components = []
    for start, value in enumerate(alpha):
        if value == 0 or visited[start]:
            continue
        queue, component = deque([start]), []
        visited[start] = 1
        while queue:
            index = queue.popleft(); component.append(index)
            x, y = index % width, index // width
            for other in (index-1 if x else -1, index+1 if x+1 < width else -1,
                          index-width if y else -1, index+width if y+1 < height else -1):
                if other >= 0 and alpha[other] and not visited[other]:
                    visited[other] = 1; queue.append(other)
        components.append(component)
    minimum = max((len(component) for component in components), default=0)*.03
    for component in components:
        if len(component) < minimum:
            for index in component:
                alpha[index] = 0
    tile.putalpha(Image.frombytes('L', tile.size, bytes(alpha)))
    return tile


def _crop_views(source, xedges):
    width, height = source.size
    alpha = source.getchannel('A').tobytes()
    seams = [[0]*height]
    for index, anchor in enumerate(xedges[1:-1], 1):
        radius = min(6, (anchor-xedges[index-1])//4, (xedges[index+1]-anchor)//4)
        seams.append(_seam(alpha, width, height, anchor, radius))
    seams.append([width]*height)
    tiles = []
    for left, right in zip(seams, seams[1:]):
        x0, x1 = min(left), max(right)
        tile = source.crop((x0, 0, x1, height))
        masked = bytearray(tile.getchannel('A').tobytes())
        for y in range(height):
            offset = y*(x1-x0)
            masked[offset:offset+left[y]-x0] = bytes(left[y]-x0)
            masked[offset+right[y]-x0:offset+x1-x0] = bytes(x1-right[y])
        tile.putalpha(Image.frombytes('L', tile.size, bytes(masked)))
        tiles.append(_trim_fragments(tile))
    return tiles


def crop_rows(image, yedges, xedges_by_row):
    """Separate rows as well as columns; long hair can extend past a row anchor."""
    from src.services.avatar_part_batches import isolate_hair
    source = isolate_hair(image)
    width, height = source.size
    horizontal = source.getchannel('A').transpose(Image.Transpose.TRANSPOSE).tobytes()
    seams = [[0]*width]
    for index, anchor in enumerate(yedges[1:-1], 1):
        radius = min(24, (anchor-yedges[index-1])//4, (yedges[index+1]-anchor)//4)
        seams.append(_seam(horizontal, height, width, anchor, radius))
    seams.append([height]*width)
    rows = []
    for top, bottom, xedges in zip(seams, seams[1:], xedges_by_row):
        y0, y1 = min(top), max(bottom)
        row = source.crop((0, y0, width, y1))
        alpha = bytearray(row.getchannel('A').tobytes())
        for x in range(width):
            for y in range(y0, top[x]):
                alpha[(y-y0)*width+x] = 0
            for y in range(bottom[x], y1):
                alpha[(y-y0)*width+x] = 0
        row.putalpha(Image.frombytes('L', row.size, bytes(alpha)))
        rows.append(_crop_views(row, xedges))
    return rows


def crop_row(image, y0, y1, xedges):
    from src.services.avatar_part_batches import isolate_hair
    return _crop_views(isolate_hair(image.crop((0, y0, image.width, y1))), xedges)
