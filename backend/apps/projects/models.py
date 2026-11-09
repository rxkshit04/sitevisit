from django.db import models


class Project(models.Model):
    name = models.CharField(max_length=120)
    rera_number = models.CharField(max_length=60)
    address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def __str__(self):
        return self.name