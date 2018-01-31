# coding: utf-8
"""mysite URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_required
import DevicesAPP.urls
from DevicesAPP.constants import APP_TEMPLATE_NAMESPACE as DEVICESAPP_TEMPLATE_NAMESPACE
import accounts.urls
import profiles.urls

from . import views

import logging

logger = logging.getLogger("project")      

urlpatterns = [
    url(r'^$', views.Home.as_view(), name='home'),
    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^about/$', views.AboutPage.as_view(), name='about'),
    url(r'^'+DEVICESAPP_TEMPLATE_NAMESPACE+'/', include(DevicesAPP.urls, namespace=DEVICESAPP_TEMPLATE_NAMESPACE)),

    url(r'^repbuilder/(?P<number>.+)/$', views.reportbuilder, name='repbuilder'),
    
    

    url(r'^charts/$', views.device_report,name='devicecharts'),
    url(r'^settimezone/$', views.settimezone,name='settimezone'),
    url(r'^advancedDevice/$', views.AdvancedDevice.as_view(),name='advancedDevice'),
    url(r'^advancedDevice/arduinoCode/$', views.arduinoCode,name='arduinoCode'),
    url(r'^reports/$', views.viewReports,name='viewReports'),
    url(r'^reports/(?P<pk>.+)/$', views.viewReports,name='viewReports'),
    url(r'^deletereports/(?P<pk>.+)/$', views.deleteReport,name='deleteReport'),
    url(r'^reportpreview/(?P<title>.+)/$', views.previewReport,name='previewReport'),
    url(r'^owntracks/(?P<user>.+)/$', views.handleLocation,name='handleLocation'),
    url(r'^userubication/$', views.viewUserUbication,name='viewUserUbication'),
    url(r'^view_schedules/$', views.viewSchedules,name='viewSchedules'),
    url(r'^activateSchedule/(?P<pk>.+)/$', views.activateSchedule,name='activateSchedule'),
    url(r'^modifySchedule/(?P<pk>.+)/(?P<value>.+)/(?P<sense>.+)/$', views.modifySchedule,name='modifySchedule'),
    url(r'^view_rules/$', views.viewRules,name='viewRules'),
    url(r'^activateRule/(?P<pk>.+)/$', views.activateRule,name='activateRule'),
    url(r'^gitupdate/$', views.GitUpdate,name='gitupdate'),
    url(r'^softreset/$', views.SoftReset,name='softreset'),
    url(r'^users/', include(profiles.urls, namespace='profiles')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^admin/Devices/setcustomlabels/(?P<devicePK>.+)/$',views.adminSetCustomLabels,name='adminSetCustomLabels'),
    url(r'^admin/RemoteDevices/setcustomlabels/(?P<connection>.+)/(?P<devicePK>.+)/$',views.adminSetCustomLabels,name='adminSetCustomLabels'),
    url(r'^admin/LocalDevices/setcustomlabels/(?P<connection>.+)/(?P<devicePK>.+)/$',views.adminSetCustomLabels,name='adminSetCustomLabels'),
    
    url(r'^', include(accounts.urls, namespace='accounts')),
    
]

handler500 = 'HomeAutomation.views.custom_error500_view'

# User-uploaded files like profile pics need to be served in development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Include django debug toolbar if DEBUG is on
if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ]
