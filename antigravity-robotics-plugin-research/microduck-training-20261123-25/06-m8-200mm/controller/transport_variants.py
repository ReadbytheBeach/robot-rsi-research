"""Bounded fallback controls for a lateral nut near the edge of the two pads."""
def variants(config):
    """Return (tag, settings) with the unmodified policy first and two mirrored fallbacks.

    The controller's carry.jaw field is in degrees and carry.head angles are radians.
    Inputs are never mutated. Test on a copy before using a fallback in the live episode.
    """
    cases=[('original',config)]
    for tag,roll in (('lighter_positive_roll',.20),('lighter_negative_roll',-.20)):
        carry=dict(config['carry'])
        carry['jaw']+=3.0
        head=list(carry['head'])
        head[3]+=roll
        carry['head']=head
        cases.append((tag,config|{'carry':carry}))
    return cases
