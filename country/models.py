from collections import defaultdict
from django.db import models

inf = 100000000  # бесконечность (позиция)
ad = 0.01  # реклама за одно скачивание бесплатного приложения


# ----------------------------------

class Category(models.Model):
    name = models.CharField(max_length=20)  # название


class Platform(models.Model):
    name = models.CharField(max_length=20)  # название


class Language(models.Model):
    name = models.CharField(max_length=20)  # название


# ----------------------------------

class World(models.Model):
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE)  # платформа

    users = models.FloatField()  # всего пользователей
    gross = models.FloatField()  # прибыль

    def save(self, *args, **kwargs):
        self.users = sum(q.users for q in Country.objects.all())

        super(World, self).save(*args, **kwargs)

    # ----------------------------------
    # оценить прибыль всех приложений

    def set_gross(self):
        for q in Users.objects.all():
            q.set_gross()

        k = self.gross / sum(q.gross for q in Gross.objects.all())

        for q in Gross.objects.all():
            q.update(downloads=q.gross * k)

    # ----------------------------------
    # оценить количество загрузок всех приложений

    def set_downloads(self):
        for q in Users.objects.all():
            q.set_downloads()

        downloads = sum(q.downloads for q in Downloads.objects.all())
        k = downloads / sum(q.downloads for q in App.objects.all())

        for q in Downloads.objects.all():
            q.update(downloads=q.downloads * k)


class Country(models.Model):
    name = models.CharField(max_length=20)  # название

    wage = models.FloatField()  # средняя зарплата пользователей
    rich = models.FloatField()  # зарплата 10 процентов самых
    poor = models.FloatField()  # зарплата 10 самых бедных

    users = models.IntegerField()  # пользователей телефонами
    populations = models.IntegerField()  # жителей страны

    language = models.ForeignKey(Language, on_delete=models.CASCADE)  # основной язык

    # ----------------------------------

    def set_rate(self):
        wages = [0] * 101

        # ----------------------------------
        # прикинуть распределение зарплат по нескольким точкам

        i = v = a = 0
        for b, j in [(self.poor, 10), (self.wage, 50), (self.rich, 90), (2 * self.rich, 100)]:
            n = j - i
            d = 2 * (b - a - n * v) / (n * n + n)
            for k in range(i, j):
                v += d
                wages[k + 1] = wages[k] + v
            i = j

        # ----------------------------------
        # прикинуть распределение покупательной способности

        A = 500
        B = 3000

        gross = [0] * 101
        for i in range(101):
            if wages[i] > A:
                gross[i] = 1 if wages[i] > B else (wages[i] - A) / (B - A)

        # ----------------------------------
        # прикинуть распределение наличия телефонов

        users = 100 * self.users / self.populations
        X = 100

        a = X + 1
        b = 10000

        while b - a > 1:
            c = (a + b) / 2
            u = 0
            for w in wages:
                if w > X:
                    u += 1 if w > c else (w - X) / (c - X)
            if u > users:
                a = c
            else:
                b = c
        Y = (a + b) / 2

        # ----------------------------------
        # прикинуть распределение пользователей iOS

        platform = Platform.objects.get(name='iOS')
        users = self.rate_set.get(platform=platform)
        users = 100 * users / self.populations

        u = 0
        B = 3000
        A = 500
        T = 1
        for w in wages:
            if w > A:
                u += 1 if w > B else (w - A) / (B - A)

        if u < users:
            a = A + 1
            b = B
            while b - a > 1:
                c = (a + b) / 2
                u = 0
                for w in wages:
                    if w > 100:
                        u += 1 if w > c else (w - 100) / (c - 100)
                if u > users:
                    a = c
                else:
                    b = c
            B = (a + b) / 2
        else:
            u = 0
            for w in wages:
                if w > A:
                    u += 1 if w > B else (w - A) / (B - A)
            T = users / u

        # ----------------------------------
        # перемножить графики и для каждго случая вычислить площадь

        platform = Platform.objects.get(name='iOS')
        r = self.rate_set.get(platform=platform)

        r.gross = 0
        r.downloads = 0

        for i, w in enumerate(wages):
            if w > A:
                t = T if w > B else T * (w - A) / (B - A)

                r.gross += gross[i] * t
                r.downloads += t
        r.save()

        platform = Platform.objects.get(name='Android')
        r = self.rate_set.get(platform=platform)

        r.gross = 0
        r.downloads = 0

        for i, w in enumerate(wages):
            if w > X:
                t = 1 if w > Y else (w - X) / (Y - X)
                if w > A:
                    t -= T if w > B else T * (w - A) / (B - A)

                r.gross += gross[i] * t
                r.downloads += t
        r.save()


# ----------------------------------
# коэффициенты

class Rate(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE)  # страна
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE)  # платформа

    users = models.IntegerField()  # пользователей

    gross = models.FloatField(default=0)  # коэффициент по прибыли
    downloads = models.FloatField(default=0)  # коэффициент по загрузкам


# ----------------------------------
# сегмент пользователей

class Users(models.Model):
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE)  # платформа
    country = models.ForeignKey(Country, on_delete=models.CASCADE)  # страна

    free = models.BooleanField(default=True)  # бесплатно

    # ----------------------------------
    # определение порядка по прибыли

    def set_gross(self):
        apps = App.objects.filter(platform=self.platform, price__isnull=self.free)
        rate = Rate.objects.get(country=self.country, platform=self.platform)

        s = {q.app: q.position for q in Gross.objects.filter(top=True)}
        k = rate.downloads * self.country.wage if self.free else rate.gross

        # ----------------------------------
        # делаем оценку прибыли

        t = []
        for app in apps:
            gross = 0
            if app.language == self.country.language:
                gross = k * app.get_gross()

            position = s.get(app, inf)

            t.append(
                Gross(
                    app=app,
                    country=self.country,

                    position=position,
                    gross=gross,
                )
            )

        # ----------------------------------
        # взвешиваем категории

        t.sort(key=lambda q: q.gross, reverse=True)
        s = [q.gross for q in t]
        t.sort(key=lambda q: q.position)
        x = {}
        y = {}
        for i, q in enumerate(t):
            y[q.app.category] += s[i]
            x[q.app.category] += q.gross

        for category in y: y[category] /= x[category]

        # ----------------------------------
        # уточняем прибыль с учетом категории

        for q in t: q.gross *= y[q.app.category]

        t.sort(key=lambda q: q.gross, reverse=True)
        s = [q.gross for q in t]
        t.sort(key=lambda q: q.position)

        for q in enumerate(t):
            q.position = i + 1
            q.gross = s[i]

        # ----------------------------------

        Gross.objects.all().delete()
        Gross.objects.bulk_create(t)

    # ----------------------------------
    # определение порядка по скачиваниям

    def set_downloads(self):
        apps = App.objects.filter(platform=self.platform, price__isnull=self.free)
        rate = Rate.objects.get(country=self.country, platform=self.platform)

        s = {q.app: q.position for q in Downloads.objects.filter(top=True)}
        k = rate.downloads

        # ----------------------------------
        # делаем оценку загрузок

        t = []
        for app in apps:
            downloads = 0
            if app.language == self.country.language:
                downloads = k * app.downloads

            position = s.get(app, inf)

            t.append(
                Downloads(
                    app=app,
                    country=self.country,

                    position=position,
                    downloads=downloads,
                )
            )

        # ----------------------------------
        # взвешиваем категории

        t.sort(key=lambda q: q.downloads, reverse=True)
        s = [q.downloads for q in t]
        t.sort(key=lambda q: q.position)
        x = {}
        y = {}
        for i, q in enumerate(t):
            y[q.app.category] += s[i]
            x[q.app.category] += q.downloads

        for category in y: y[category] /= x[category]

        # ----------------------------------
        # уточняем скачивание с учетом категории

        for q in t: q.downloads *= y[q.app.category]

        t.sort(key=lambda q: q.downloads, reverse=True)
        s = [q.downloads for q in t]
        t.sort(key=lambda q: q.position)

        for q in enumerate(t):
            q.position = i + 1
            q.downloads = s[i]

        # ----------------------------------

        Downloads.objects.all().delete()
        Downloads.objects.bulk_create(t)


# ----------------------------------
# вычисление коэффицинтов

# ----------------------------------
# прибыль

class App(models.Model):
    name = models.CharField(max_length=20)  # название

    platform = models.ForeignKey(Platform, on_delete=models.CASCADE)  # платформа
    category = models.ForeignKey(Category, on_delete=models.CASCADE)  # категория

    price = models.FloatField(default=0)  # сколько стоит
    language = models.ForeignKey(Language, on_delete=models.CASCADE)  # язык приложения

    downloads = models.IntegerField()  # количество загрузок (известно)
    gross = models.FloatField()  # прибыль (оценка)

    # ----------------------------------
    # примитивная оценка прибыли

    def get_gross(self):
        return self.downloads * min(self.price, ad)


# ----------------------------------
# прибыль

class Gross(models.Model):
    app = models.ForeignKey(App, on_delete=models.CASCADE)
    country = models.ForeignKey(Country, on_delete=models.CASCADE)

    top = models.BooleanField(default=False)  # в топе

    position = models.IntegerField(default=inf)  # позиция в стране
    gross = models.FloatField()  # прибыль


# ----------------------------------
# загрузки

class Downloads(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    app = models.ForeignKey(App, on_delete=models.CASCADE)

    top = models.BooleanField(default=False)  # в топе

    position = models.IntegerField(default=inf)  # позиция в стране
    downloads = models.IntegerField()  # количество скачиваний


# ----------------------------------
# оценка числа загрузок и списка стран с наибольшим числом скачиваний

def get_downloads(category, platform, language, free, best=0.5, count=5):
    u = []
    d = defaultdict(list)
    for app in App.objects.filter(
            category=category,
            platform=platform,
            language=language,
            price__isnull=free
    ):
        u.append(app.downloads)
        for q in Downloads.objects.filter(app=app):
            d[q.country].append(q.downloads)

    t = []
    for k, v in d.items():
        v.sort(reverse=True)
        v = v[int(best * len(v))]
        t.append((v, k))
    t.sort(reverse=True)

    u.sort(reverse=True)
    v = u[int(best * len(u))]

    return (v, t[:count])


# ----------------------------------
# оценка прибыли и списка стран с наибольшим доходом

def get_gross(category, platform, language, free, best=0.5, count=5):
    u = []
    d = defaultdict(list)
    for app in App.objects.filter(
            category=category,
            platform=platform,
            language=language,
            price__isnull=free
    ):
        u.append(app.gross)
        for q in Gross.objects.filter(app=app):
            d[q.country].append(q.gross)

    t = []
    for k, v in d.items():
        v.sort(reverse=True)
        v = v[int(best * len(v))]
        t.append((v, k))
    t.sort(reverse=True)

    u.sort(reverse=True)
    v = u[int(best * len(u))]

    return (v, t[:count])
