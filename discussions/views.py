
from djangohelpers.lib import rendered_with
from djangohelpers.lib import allow_http

from django.db.models import get_model


from discussions.models import Discussion
from structuredcollaboration.models import Collaboration
from django.http import HttpResponseForbidden, HttpResponseServerError
from django.shortcuts import get_object_or_404
from django.core.urlresolvers import reverse,resolve
from django.contrib.contenttypes.models import ContentType
from threadedcomments import ThreadedComment

from courseaffils.lib import in_course_or_404
from projects.forms import ProjectForm
from projects.models import Project
from courseaffils.models import Course
from django.http import HttpResponseRedirect


from assetmgr.lib import most_popular,annotated_by

import pdb

Asset = get_model('assetmgr','asset')


#TODO: check user is logged in before displaying

@allow_http("GET")
@rendered_with('discussions/show_discussion.html')
def show(request, discussion_id):
    """Show a threadedcomments discussion of an arbitrary object.
    discussion_id is the pk of the root comment."""
    root_comment = get_object_or_404(ThreadedComment, pk = discussion_id)

    #for_now:
    space_viewer = request.user
    space_owner = request.user
    
    if request.GET.has_key('as') and request.user.is_staff:
        space_viewer = get_object_or_404(User, username=request.GET['as'])

    if not root_comment.content_object.permission_to('read',request):
        return HttpResponseForbidden('You do not have permission to view this discussion.')
    
    try:
        my_course = root_comment.content_object.context.content_object
    except:
        #temporary:
        my_courses = [c for c in Course.objects.all() if request.user in c.members]
        my_course = my_courses[-1]
        root_comment.content_object.context = Collaboration.get_associated_collab(my_course)

    assets = annotated_by(Asset.objects.filter(course=my_course), space_viewer)

    return {
        'is_space_owner': True,
        'edit_comment_permission': my_course.is_faculty,
        'space_owner': space_owner,
        'space_viewer': space_viewer,
        'root_comment': root_comment,
        'assets': assets,
        'page_in_edit_mode': True,
        }
        
        


@allow_http("POST")
def new(request):
    """Start a discussion of an arbitrary model instance."""
    #pdb.set_trace()
    rp = request.POST
    app_label, model, obj_pk, comment_html =  ( rp['app_label'], rp['model'], rp['obj_pk'], rp['comment_html'] )
    #Find the object we're discussing.
    the_content_type = ContentType.objects.get(app_label=app_label, model=model)
    assert the_content_type != None
    
    the_object = the_content_type.get_object_for_this_type(pk = obj_pk)
    assert the_object != None
    
    
    try:
        obj_sc = Collaboration.get_associated_collab(the_object)
    except Collaboration.DoesNotExist:
        obj_sc = Collaboration()
        #TODO: populate this collab with sensible auth defaults.
        obj_sc.content_object = the_object
        obj_sc.save()
    

    #sky: I think what I want to do is have the ThreadedComment
    #point to the_object
    #and the collaboration will point to the threaded root comment
    #that way, whereas, if we live in Collaboration-land, we can get to ThreadedComments
    # threaded comments can also live in it's own world without 'knowing' about SC
    # OTOH, threaded comment shouldn't be able to point to the regular object
    # until Collaboration says it's OK (i.e. has permissions)

    #now create the CHILD collaboration object for the discussion to point at.
    #This represents the auth for the discussion itself.
    disc_sc = Collaboration(_parent=obj_sc,
                            title=comment_html,
                            #or we could point it at the root threadedcomments object.
                            #content_object=None,
                            context=request.collaboration_context,
                            )
    disc_sc.save()

    #finally create the root discussion object, pointing it at the CHILD.
    #TODO point the context at the course
    new_threaded_comment = ThreadedComment(parent=None, 
                                           title=comment_html,
                                           comment=comment_html, 
                                           user=request.user, 
                                           content_object=disc_sc)
    
    #TODO: find the default site_id
    new_threaded_comment.site_id = 1
    new_threaded_comment.save()
    return HttpResponseRedirect( "/discussion/show/%d" % new_threaded_comment.id )
    

@allow_http("POST")    
@rendered_with('comments/posted.html')
def comment_change(request, comment_id, next=None):
    "save comment, since comments/post only does add, no edit"
    comment = ThreadedComment.objects.get(pk=comment_id)
    if not comment.content_object.permission_to('edit',request):
        return HttpResponseForbidden('You do not have permission to edit this discussion.')

    comment.comment = request.POST['comment']
    comment.title = request.POST['title']

    comment.save()
    return {
        'comment': comment,
        }
    
