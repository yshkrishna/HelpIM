from django.conf.urls.defaults import patterns, url, include
from django.views.generic.simple import direct_to_template

from registration.views import activate
from registration.views import register

urlpatterns = patterns(
    '',
    url(r'^$', 'helpim.buddychat.views.welcome'),
    url(r'^admin/chatbuddies/$', 'helpim.buddychat.views.chatbuddies', name='chatbuddies_list'),
    url(r'^profile/(?P<username>\w+)/$', 'helpim.buddychat.views.profile', name='buddychat_profile'),
    url(r'^profile/(?P<username>\w+)/chat$', 'helpim.buddychat.views.join_chat', name='buddychat_chat'),
    url(r'^profile/(?P<username>\w+)/set_cw$', 'helpim.buddychat.views.set_cw'),
    url(r'^activate/complete/$',
        direct_to_template,
        { 'template': 'registration/activation_complete.html' },
        name='registration_activation_complete'),
    # Activation keys get matched by \w+ instead of the more specific
    # [a-fA-F0-9]{40} because a bad activation key should still get to the view;
    # that way it can return a sensible "invalid key" message instead of a
    # confusing 404.
    url(r'^activate/(?P<activation_key>\w+)/$',
        activate,
        { 'backend': 'helpim.buddychat.registration_backends.BuddyChatBackend' },
        name='registration_activate'),
    url(r'^register/$',
        register,
        { 'backend': 'helpim.buddychat.registration_backends.BuddyChatBackend' },
        name='registration_register'),
    url(r'^register/complete/$',
        direct_to_template,
        { 'template': 'registration/registration_complete.html' },
        name='registration_complete'),
    url(r'^register/closed/$',
        direct_to_template,
        { 'template': 'registration/registration_closed.html' },
        name='registration_disallowed'),
    (r'', include('registration.auth_urls')),
    )
    
