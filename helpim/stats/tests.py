from datetime import date, datetime

from django.contrib.auth.models import ContentType, Permission, User
from django.core.urlresolvers import resolve, Resolver404, reverse
from django.test import TestCase
from django.test.client import Client
from django.utils.translation import ugettext as _

from helpim.common.models import BranchOffice
from helpim.conversations.models import Chat, ChatMessage
from helpim.stats.forms import ReportForm
from helpim.stats.models import BranchReportVariable, CareworkerReportVariable, ConversationFormsReportVariable, DurationReportVariable, HourReportVariable, MonthReportVariable, NoneReportVariable, Report, ReportVariable, WaitingTimeReportVariable, WeekdayReportVariable


class UrlPatternsTestCase(TestCase):
    '''Test url design of stats app'''

    # base url where stats app runs
    base_url = "/admin/stats/"

    def setUp(self):
        super(UrlPatternsTestCase, self).setUp()

        self.c = Client()
        self.user = User.objects.create_user('testuser', 'test@example.com', 'test')
        c, created = ContentType.objects.get_or_create(model='', app_label='stats',
                                                       defaults={'name': 'stats'})
        p, created = Permission.objects.get_or_create(codename='can_view_stats', content_type=c,
                                                      defaults={'name': 'Can view Stats', 'content_type': c})
        self.user.user_permissions.add(p)
        self.assertTrue(self.c.login(username=self.user.username, password='test'), 'Could not login')


    def _assertUrlMapping(self, url, action, params={}, follow=True):
        '''assert that when `url` is accessed, the view `action` is invoked with parameters dictionary `params`'''

        response = self.c.get(self.base_url + url, follow=follow)
        self.assertTrue(response.status_code != 404, 'URL not found')

        try:
            info = resolve(response.request["PATH_INFO"])
        except Resolver404:
            self.fail("Could not resolve '%s'" % (response.request["PATH_INFO"]))

        self.assertEqual(info.url_name, action, "view name is '%s', but '%s' was expected" % (info.url_name, action))
        self.assertEqual(len(info.kwargs), len(params), 'Number of parameters does not match: expected: %s -- got: %s' % (params, info.kwargs))

        for key, value in params.items():
            self.assertTrue(key in info.kwargs, 'Expected parameter "%s" not found' % (key))
            self.assertEqual(info.kwargs[key], value, 'Values for parameter "%s" do not match: "%s" != "%s"' % (key, info.kwargs[key], value))


    def testStatsUrlMappings(self):
        '''test url mappings for general stats functionality'''

        self._assertUrlMapping('', 'stats_index')

        self._assertUrlMapping('chat', 'stats_overview', {'keyword': 'chat'})
        self._assertUrlMapping('chat/', 'stats_overview', {'keyword': 'chat'})

        self._assertUrlMapping('chat/1999', 'stats_overview', {'keyword': 'chat', 'year': '1999'})
        self._assertUrlMapping('chat/1999/', 'stats_overview', {'keyword': 'chat', 'year': '1999'})

        self._assertUrlMapping('chat/2011/csv', 'stats_overview', {'keyword': 'chat', 'year': '2011', 'format': 'csv'})
        self._assertUrlMapping('chat/2011/csv/', 'stats_overview', {'keyword': 'chat', 'year': '2011', 'format': 'csv'})

        self.assertRaisesRegexp(AssertionError, 'URL not found',
                                lambda: self._assertUrlMapping('keyworddoesntexist', 'stats_overview'))


    def testReportsUrlMappings(self):
        '''test url mappings for reports functionality'''

        # create Report with specific id to be used throughout test
        r = Report(period_start=date(2000, 1, 1), period_end=date(2000, 1, 1), variable1='weekday', variable2='branch')
        r.save()
        r.id = 4143
        r.save()

        self._assertUrlMapping('reports/new/', 'report_new')
        self._assertUrlMapping('reports/4143/', 'report_show', {'id': '4143'})
        self._assertUrlMapping('reports/4143/edit/', 'report_edit', {'id': '4143'})
        self._assertUrlMapping('reports/4143/delete/', 'report_delete', {'id': '4143'}, follow=False)


    def testPermission(self):
        # access allowed for privileged user
        response = self.c.get(reverse('stats_index'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'stats/stats_index.html')


        # test access to stats with unprivileged user
        self.c = Client()
        unprivilegedUser = User.objects.create_user('bob', 'me@bob.com', 'bob')
        self.assertTrue(self.c.login(username=unprivilegedUser.username, password='bob'), 'Bob could not login')

        response = self.c.get(reverse('stats_index'))
        self.assertNotEqual(response.status_code, 200)
        self.assertTemplateNotUsed(response, 'stats/stats_index.html')


class ReportTestCase(TestCase):
    fixtures = ['reports-test.json']

    def test_matching_chats(self):
        r = Report.objects.get(pk=1)
        r.period_start = date(2010, 1, 1)
        r.period_end = date(2010, 1, 1)

        chats = r.matching_chats()
        self.assertItemsEqual(Chat.objects.filter(id__in=[1]), chats)

        # remove lower bound
        r.period_start = None
        chats = r.matching_chats()
        self.assertItemsEqual(Chat.objects.filter(id__in=[1, 2]), chats)

        # remove upper bound
        r.period_end = None
        chats = r.matching_chats()
        self.assertItemsEqual(Chat.objects.all(), chats)

        # set careworker only
        r.careworker = User.objects.get(pk=55)
        chats = r.matching_chats()
        self.assertItemsEqual(Chat.objects.filter(id__in=[2]), chats)

        # set branch office only
        r.careworker = None
        r.branch = BranchOffice.objects.get(pk=1)
        chats = r.matching_chats()
        self.assertItemsEqual(Chat.objects.filter(id__in=[2, 3]), chats)

        # set branch and careworker
        r.careworker = User.objects.get(pk=22)
        chats = r.matching_chats()
        self.assertItemsEqual(Chat.objects.filter(id__in=[3]), chats)

    def test_apply_filters(self):
        r = Report.objects.get(pk=1)
        c1 = Chat.objects.get(pk=1)
        c2 = Chat.objects.get(pk=2)
        c3 = Chat.objects.get(pk=3)

        # r doesnt have any filters set
        self.assertEqual(True, r.apply_filters(c1))
        self.assertEqual(True, r.apply_filters(c2))
        self.assertEqual(True, r.apply_filters(c3))

    def test_filter_blocked(self):
        r = Report.objects.get(pk=1)
        c1 = Chat.objects.get(pk=1)

        # set filtering
        r.filter_blocked = True
        self.assertEqual(True, r.apply_filters(c1))

        # block client
        p = c1.getClient()
        p.blocked = True
        p.save()
        self.assertEqual(False, r.apply_filters(c1))

    def test_filter_assigned(self):
        r = Report.objects.get(pk=1)
        c1 = Chat.objects.get(pk=1)

        # set filtering
        r.filter_assigned = True
        self.assertEqual(True, r.apply_filters(c1))

        # make c1 un-assigned
        c1.getStaff().delete()
        self.assertEqual(False, r.apply_filters(c1))

        c1.getClient().delete()
        self.assertEqual(False, r.apply_filters(c1))

    def test_filter_interactive(self):
        r = Report.objects.get(pk=1)
        c1 = Chat.objects.get(pk=1)

        # set filtering
        r.filter_interactive = True
        self.assertEqual(False, r.apply_filters(c1))

        # make c1 interactive by adding message from both participants
        ChatMessage(conversation=c1, sender=c1.getClient(), sender_name=c1.getClient().name, created_at=datetime.now(), body="?").save()
        ChatMessage(conversation=c1, sender=c1.getStaff(), sender_name=c1.getStaff().name, created_at=datetime.now(), body="!").save()
        self.assertEqual(True, r.apply_filters(c1))

    def test_filter_queued(self):
        r = Report.objects.get(pk=1)
        c1 = Chat.objects.get(pk=1)

        # set filtering
        r.filter_queued = True
        self.assertEqual(False, r.apply_filters(c1))

        # waiting time below threshold, c1 doesnt pass filters
        c1._waiting_time = 0
        self.assertEqual(False, r.apply_filters(c1))

        # make c1 queued
        c1._waiting_time = 3000
        self.assertEqual(True, r.apply_filters(c1))

    def test_generate_2variables(self):
        r = Report.objects.get(pk=1)

        data = r.generate()['rendered_report']
        self.assertTrue(len(data) > 0)

        # determine number of cells
        cells = 0
        for col in data.iterkeys():
            for cell in data[col].iterkeys():
                cells += 1

        # +1 for 'Total' column
        var1_samples = list(ReportVariable.find_variable(r.variable1).values())
        var2_samples = list(ReportVariable.find_variable(r.variable2).values())
        self.assertEqual((len(var1_samples) + 1) * (len(var2_samples) + 1), cells)

        # cells
        self.assertEqual(1, data[_('Thursday')]['Office Amsterdam'])
        self.assertEqual(1, data[_('Friday')][Report.OTHER_COLUMN])
        self.assertEqual(1, data[_('Saturday')]['Office Amsterdam'])

        # row sums
        self.assertEqual(2, data[Report.TOTAL_COLUMN]['Office Amsterdam'])
        self.assertEqual(1, data[Report.TOTAL_COLUMN][Report.OTHER_COLUMN])

        # col sums
        self.assertEqual(1, data[_('Thursday')][Report.TOTAL_COLUMN])
        self.assertEqual(1, data[_('Friday')][Report.TOTAL_COLUMN])
        self.assertEqual(1, data[_('Saturday')][Report.TOTAL_COLUMN])

        # table sum
        self.assertEqual(3, data[Report.TOTAL_COLUMN][Report.TOTAL_COLUMN])

    def test_generate_1variable(self):
        r = Report.objects.get(pk=1)

        # remove variable2
        r.variable2 = NoneReportVariable.get_choices_tuples()[0][0]

        data = r.generate()['rendered_report']
        self.assertTrue(len(data) > 0)

        # determine number of cells
        cells = 0
        for col in data.iterkeys():
            for cell in data[col].iterkeys():
                cells += 1

        # +1 for 'Total' column
        var1_samples = list(ReportVariable.find_variable(r.variable1).values())
        var2_samples = list(ReportVariable.find_variable(r.variable2).values())
        self.assertEqual((len(var1_samples) + 1) * (len(var2_samples) + 1), cells)

        # cells
        self.assertEqual(1, data[_('Thursday')][NoneReportVariable.EMPTY])
        self.assertEqual(1, data[_('Friday')][NoneReportVariable.EMPTY])
        self.assertEqual(1, data[_('Saturday')][NoneReportVariable.EMPTY])

        # row sums
        self.assertEqual(3, data[Report.TOTAL_COLUMN][NoneReportVariable.EMPTY])

        # col sums
        self.assertEqual(1, data[_('Thursday')][Report.TOTAL_COLUMN])
        self.assertEqual(1, data[_('Friday')][Report.TOTAL_COLUMN])
        self.assertEqual(1, data[_('Saturday')][Report.TOTAL_COLUMN])

        # table sum
        self.assertEqual(3, data[Report.TOTAL_COLUMN][Report.TOTAL_COLUMN])

    def test_generate_0variables(self):
        r = Report.objects.get(pk=1)

        # remove both variables
        r.variable1 = NoneReportVariable.get_choices_tuples()[0][0]
        r.variable2 = NoneReportVariable.get_choices_tuples()[0][0]

        data = r.generate()['rendered_report']
        self.assertTrue(len(data) > 0)

        # determine number of cells
        cells = 0
        for col in data.iterkeys():
            for cell in data[col].iterkeys():
                cells += 1

        # +1 for 'Total' column
        var1_samples = list(ReportVariable.find_variable(r.variable1).values())
        var2_samples = list(ReportVariable.find_variable(r.variable2).values())
        self.assertEqual((len(var1_samples) + 1) * (len(var2_samples) + 1), cells)

        # cells
        self.assertEqual(3, data[NoneReportVariable.EMPTY][NoneReportVariable.EMPTY])

        # row/col/table sums
        self.assertEqual(3, data[Report.TOTAL_COLUMN][NoneReportVariable.EMPTY])
        self.assertEqual(3, data[NoneReportVariable.EMPTY][Report.TOTAL_COLUMN])
        self.assertEqual(3, data[Report.TOTAL_COLUMN][Report.TOTAL_COLUMN])

    def test_generate_0variables_unique(self):
        r = Report.objects.get(pk=1)
        r.variable1 = NoneReportVariable.get_choices_tuples()[0][0]
        r.variable2 = NoneReportVariable.get_choices_tuples()[0][0]
        r.output = 'unique'

        data = r.generate()['rendered_report']
        self.assertTrue(len(data) > 0)

        # cells
        self.assertEqual(2, data[NoneReportVariable.EMPTY][NoneReportVariable.EMPTY])

        # row/col/table sums
        self.assertEqual(2, data[Report.TOTAL_COLUMN][NoneReportVariable.EMPTY])
        self.assertEqual(2, data[NoneReportVariable.EMPTY][Report.TOTAL_COLUMN])
        self.assertEqual(2, data[Report.TOTAL_COLUMN][Report.TOTAL_COLUMN])


class ReportFormTestCase(TestCase):
    def test_clean_period(self):
        form = ReportForm(data={ 'period_start': date(2012, 1, 1),
            'period_end': date(1999, 1, 1),
            'title': 'test',
            'variable1': 'none',
            'variable2': 'none',
            'output': 'hits',
        })

        self.assertFalse(form.is_valid(), 'ReportForm validation should have failed because selected time period is empty')
        self.assertEqual(form.errors['__all__'], [_('The period of time you selected is invalid (end date is older than start date).')])


class ReportVariableTestCase(TestCase):
    def setUp(self):
        super(ReportVariableTestCase, self).setUp()

        # clear state, might have been set by previous tests
        ReportVariable.known_variables = {}
        self.assertEqual(0, len(ReportVariable.known_variables), "No variables should be registered")

    def test_register_variable(self):
        # test adding multiple choices at once, create mocking Variable that just has the one function needed
        ReportVariable._register_variable(type('TestReportVariable', (ReportVariable,),
          { 'get_choices_tuples': classmethod(lambda cls: [('v1', _('Var1')), ('v2', _('Var2'))]) }
        ))

        self.assertTrue(len(ReportVariable.known_variables) == 2)
        self.assertItemsEqual(['v1', 'v2'], ReportVariable.known_variables.keys())

    def test_all_variables(self):
        # calling all_variables() triggers auto-discovery and addition of variables
        self.assertTrue(WeekdayReportVariable in ReportVariable.all_variables(), "Weekday variable should be registered")
        self.assertTrue(len(ReportVariable.known_variables) > 0, "There should be variables registered")

        # all_variables() must return unique list of variables
        ReportVariable.known_variables = {}
        ReportVariable._register_variable(type('TestReportVariable', (ReportVariable,),
          { 'get_choices_tuples': classmethod(lambda cls: [('v1', _('Var1')), ('v2', _('Var2'))]) }
        ))

        # TestReportVariable appears only once, although it registered 2 choices
        self.assertEqual(2, len(ReportVariable.known_variables))
        self.assertEqual(1, len(ReportVariable.all_variables()))

    def test_find(self):
        # discover Variable classes
        ReportVariable.all_variables()

        # successful lookup
        self.assertEqual(WeekdayReportVariable, ReportVariable.find_variable('weekday'))
        self.assertItemsEqual([('weekday', _('Weekday'))], ReportVariable.find_variable('weekday').get_choices_tuples())

        # fallbacks
        self.assertEqual(NoneReportVariable, ReportVariable.find_variable('doesntexist'))
        self.assertEqual(NoneReportVariable, ReportVariable.find_variable(None))


class HourReportVariableTestCase(TestCase):
    fixtures = ['reports-test.json']

    def test_values(self):
        # 24 hours in a day, +1 for Other/No value
        self.assertEqual(24 + 1, len(HourReportVariable.values()))

    def test_extract(self):
        c1 = Chat.objects.get(pk=1)
        c2 = Chat.objects.get(pk=2)
        c3 = Chat.objects.get(pk=3)

        self.assertEqual(15, HourReportVariable.extract_value(c1))
        self.assertEqual(0, HourReportVariable.extract_value(c2))
        self.assertEqual(21, HourReportVariable.extract_value(c3))

class WeekdayReportVariableTestCase(TestCase):
    fixtures = ['reports-test.json']

    def test_values(self):
        # 7 weekdays, +1 for Other/No value
        self.assertEqual(7 + 1, len(WeekdayReportVariable.values()))

    def test_extract(self):
        c1 = Chat.objects.get(pk=1)
        c2 = Chat.objects.get(pk=2)
        c3 = Chat.objects.get(pk=3)

        self.assertEqual(_('Friday'), WeekdayReportVariable.extract_value(c1))
        self.assertEqual(_('Thursday'), WeekdayReportVariable.extract_value(c2))
        self.assertEqual(_('Saturday'), WeekdayReportVariable.extract_value(c3))

class MonthReportVariableTestCase(TestCase):
    fixtures = ['reports-test.json']

    def test_values(self):
        # 12 months, +1 for Other/No value
        self.assertEqual(12 + 1, len(MonthReportVariable.values()))

    def test_extract(self):
        c1 = Chat.objects.get(pk=1)
        c2 = Chat.objects.get(pk=2)
        c3 = Chat.objects.get(pk=3)

        self.assertEqual(_('January'), MonthReportVariable.extract_value(c1))
        self.assertEqual(_('May'), MonthReportVariable.extract_value(c2))
        self.assertEqual(_('December'), MonthReportVariable.extract_value(c3))

class BranchReportVariableTestCase(TestCase):
    fixtures = ['reports-test.json']

    def test_values(self):
        # +1 for Other/No value
        self.assertEqual(len(BranchOffice.objects.distinct()) + 1, len(list(BranchReportVariable.values())))

        self.assertTrue('Office Amsterdam' in BranchReportVariable.values())
        self.assertTrue('Office Rotterdam' in BranchReportVariable.values())

    def test_extract(self):
        c1 = Chat.objects.get(pk=1)
        c2 = Chat.objects.get(pk=2)
        c3 = Chat.objects.get(pk=3)

        self.assertEqual(Report.OTHER_COLUMN, BranchReportVariable.extract_value(c1))
        self.assertEqual('Office Amsterdam', BranchReportVariable.extract_value(c2))
        self.assertEqual('Office Amsterdam', BranchReportVariable.extract_value(c3))

class CareworkerReportVariableTestCase(TestCase):
    fixtures = ['reports-test.json']

    def test_values(self):
        # +1 for Other/No value
        self.assertEqual(2 + 1, len(list(CareworkerReportVariable.values())))
        self.assertItemsEqual(['careworker', 'elseone', Report.OTHER_COLUMN], CareworkerReportVariable.values())

    def test_extract(self):
        c1 = Chat.objects.get(pk=1)
        c2 = Chat.objects.get(pk=2)
        c3 = Chat.objects.get(pk=3)

        self.assertEqual(Report.OTHER_COLUMN, CareworkerReportVariable.extract_value(c1))
        self.assertEqual('careworker', CareworkerReportVariable.extract_value(c2))
        self.assertEqual('elseone', CareworkerReportVariable.extract_value(c3))

class NoneReportVariableTestCase(TestCase):
    fixtures = ['reports-test.json']

    def test_values(self):
        self.assertEqual(1, len(list(NoneReportVariable.values())))
        self.assertTrue(NoneReportVariable.EMPTY in NoneReportVariable.values())

    def test_extract(self):
        c1 = Chat.objects.get(pk=1)
        c2 = Chat.objects.get(pk=2)
        c3 = Chat.objects.get(pk=3)

        self.assertEqual(NoneReportVariable.EMPTY, NoneReportVariable.extract_value(c1))
        self.assertEqual(NoneReportVariable.EMPTY, NoneReportVariable.extract_value(c2))
        self.assertEqual(NoneReportVariable.EMPTY, NoneReportVariable.extract_value(c3))

class DurationReportVariableTestCase(TestCase):
    fixtures = ['reports-test.json']

    def test_values(self):
        # +1 for Other/No value
        self.assertEqual(6 + 1, len(DurationReportVariable.values()))

    def test_extract(self):
        c1 = Chat.objects.get(pk=1)
        c2 = Chat.objects.get(pk=2)
        c3 = Chat.objects.get(pk=3)

        self.assertEqual(_('0-5'), DurationReportVariable.extract_value(c1))
        self.assertEqual(_('10-15'), DurationReportVariable.extract_value(c2))
        self.assertEqual(_('45+'), DurationReportVariable.extract_value(c3))

class WaitingTimeReportVariableTestCase(TestCase):
    fixtures = ['reports-test.json']

    def test_values(self):
        # +1 for Other/No value
        self.assertEqual(6 + 1, len(WaitingTimeReportVariable.values()))

    def test_extract(self):
        c1 = Chat.objects.get(pk=1)
        c2 = Chat.objects.get(pk=2)
        c3 = Chat.objects.get(pk=3)

        c1._waiting_time = 5
        c2._waiting_time = 7 * 60

        self.assertEqual(_('0-1'), WaitingTimeReportVariable.extract_value(c1))
        self.assertEqual(_('5-10'), WaitingTimeReportVariable.extract_value(c2))
        self.assertEqual(Report.OTHER_COLUMN, WaitingTimeReportVariable.extract_value(c3))

class ConversationFormsReportVariableTestCase(TestCase):
    fixtures = ['reports-test.json']

    def test_get_choices_tuples(self):
        self.assertEqual(2, len(list(ConversationFormsReportVariable.get_choices_tuples())))

    def test_values(self):
        self.assertItemsEqual(['yellow', 'red', 'blue', Report.OTHER_COLUMN], ConversationFormsReportVariable.values(1))
        self.assertItemsEqual([Report.OTHER_COLUMN], ConversationFormsReportVariable.values(2))

    def test_extract(self):
        c1 = Chat.objects.get(pk=1)
        c2 = Chat.objects.get(pk=2)
        c3 = Chat.objects.get(pk=3)

        self.assertEqual('yellow', ConversationFormsReportVariable.extract_value(c1, 1))
        self.assertEqual('red', ConversationFormsReportVariable.extract_value(c2, 1))
        self.assertEqual('blue', ConversationFormsReportVariable.extract_value(c3, 1))

        self.assertEqual(Report.OTHER_COLUMN, ConversationFormsReportVariable.extract_value(c1, 2))
        self.assertEqual(Report.OTHER_COLUMN, ConversationFormsReportVariable.extract_value(c2, 2))
        self.assertEqual(Report.OTHER_COLUMN, ConversationFormsReportVariable.extract_value(c3, 2))
