from django.db import models


class ActiveIngredient(models.Model):
    name = models.CharField(max_length=200, unique=True)
    standard_name = models.CharField(max_length=200, unique=True)
    aliases = models.TextField(
        blank=True,
        help_text='Reviewed alternate names, one per line. Do not add unverified synonyms.',
    )
    source_name = models.CharField(max_length=200, blank=True)
    source_url = models.URLField(blank=True)
    last_verified = models.DateField(null=True, blank=True)
    information_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Medicine(models.Model):
    name = models.CharField(max_length=200)
    active_ingredient = models.CharField(
        max_length=200,
        help_text='Legacy display text. Add standardized composition using the ingredient rows below.',
    )
    ingredients = models.ManyToManyField(
        ActiveIngredient,
        through='MedicineIngredient',
        blank=True,
        related_name='medicines',
    )
    dosage_form = models.CharField(max_length=80)
    strength = models.CharField(max_length=80, blank=True)
    category = models.CharField(max_length=120, default='general')
    description = models.TextField()
    warnings = models.TextField(blank=True)
    side_effects = models.TextField(blank=True)
    interactions = models.TextField(blank=True)
    contraindications = models.TextField(blank=True)
    is_non_prescription = models.BooleanField(
        default=False,
        help_text='Enable only for medicines confirmed to be non-prescription in the intended region.',
    )
    source_name = models.CharField(max_length=200, blank=True)
    source_url = models.URLField(blank=True)
    last_verified = models.DateField(null=True, blank=True)
    safety_data_verified = models.BooleanField(
        default=False,
        help_text='Enable only when composition and safety content have been checked against the cited source.',
    )
    slug = models.SlugField(unique=True)

    @property
    def has_verified_composition(self):
        if not (
            self.safety_data_verified
            and self.source_name
            and self.source_url
            and self.last_verified
        ):
            return False
        ingredients = list(self.ingredients.all())
        return bool(ingredients) and all(
            ingredient.information_verified
            and ingredient.source_name
            and ingredient.source_url
            and ingredient.last_verified
            for ingredient in ingredients
        )

    def __str__(self):
        return self.name


class MedicineIngredient(models.Model):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(ActiveIngredient, on_delete=models.PROTECT)
    strength = models.CharField(max_length=80, blank=True)
    unit = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('medicine', 'ingredient'),
                name='unique_medicine_active_ingredient',
            ),
        ]

    def __str__(self):
        return f'{self.medicine} - {self.ingredient}'
