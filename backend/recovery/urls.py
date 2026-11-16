from rest_framework.routers import DefaultRouter

from .views import RecoveryClaimViewSet


app_name = "recovery"

router = DefaultRouter()
router.register("claims", RecoveryClaimViewSet, basename="claim")

urlpatterns = router.urls