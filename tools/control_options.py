"""Scene and camera options shared by the Windows and DOS runners."""
def add_control_arguments(parser):
    parser.add_argument('--freeze',action='store_true')
    parser.add_argument('--orbit',action='store_true')
    parser.add_argument('--camera',choices=['free','orbit'])
    parser.add_argument('--animations',choices=['on','off'])
    parser.add_argument('--camera-motion',choices=['on','off'])
    parser.add_argument('--no-animations',action='store_true')

def control_arguments(args):
    result=[]
    for flag in ('freeze','orbit','no_animations'):
        if getattr(args,flag,False):result+=['--'+flag.replace('_','-')]
    for option in ('camera','animations','camera_motion'):
        value=getattr(args,option,None)
        if value is not None:result+=['--'+option.replace('_','-'),value]
    return result
