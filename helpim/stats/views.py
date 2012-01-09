import csv
import datetime
import xlwt

from django.contrib.auth.decorators import permission_required
from django.http import Http404, HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext

from helpim.conversations.stats import ChatStatsProvider

@permission_required('stats.can_view_stats', '/admin')
def stats_overview(request, keyword, year=None, format=None):
    """Display tabular stats"""

    # find StatsProvider that will collect stats
    statsProvider = _getStatsProvider(keyword)
    if statsProvider is None:
        raise Http404('No stats for this keyword')

    # default to current year
    if year is None:
        year = datetime.datetime.now().year
    try:
        year = int(year)
    except ValueError:
        year = datetime.datetime.now().year


    # list of years with Conversations needed for navigation
    listOfPages = statsProvider.countObjects()

    # get index of current year in listOfPages
    currentPageIndex = next((index for (index, x) in enumerate(listOfPages) if x["value"] == year), None)

    if currentPageIndex is not None:
        prevPageIndex = currentPageIndex - 1 if currentPageIndex > 0 else None
        nextPageIndex = currentPageIndex + 1 if currentPageIndex < len(listOfPages) - 1 else None
    else:
        prevPageIndex = None
        nextPageIndex = None

    # generate stats about current year's Conversations
    currentYearChats = statsProvider.aggregateObjects(year)
    dictStats = statsProvider.render(currentYearChats)

    # generate table header
    # look at dict of first entry and translate dict's keys
    if len(dictStats) > 0:
        tableHeadings = [statsProvider.getStatTranslation(h) for h in dictStats.itervalues().next().iterkeys()]
    else:
        tableHeadings = []

    # output data in format according to parameter in url
    if format == 'csv':
        return _stats_overview_csv(tableHeadings, dictStats, keyword, year)
    elif format == 'xls':
        return _stats_overview_xls(tableHeadings, dictStats, keyword, year)
    else:
        return render_to_response("stats/stats_overview.html",
            {'statsKeyword': keyword,
            'detail_url': statsProvider.get_detail_url(),
            'currentPage': listOfPages[currentPageIndex] if not currentPageIndex is None else {'count': 0, 'value': year},
            'prevPage': listOfPages[prevPageIndex] if not prevPageIndex is None else None,
            'nextPage': listOfPages[nextPageIndex] if not nextPageIndex is None else None,
            'pagingYears': listOfPages,
            'tableHeadings': tableHeadings,
            'aggregatedStats': dictStats },
            context_instance=RequestContext(request))


@permission_required('stats.can_view_stats', '/admin')
def stats_index(request):
    '''Display overview showing available StatProviders'''

    return render_to_response('stats/stats_index.html',
        {'statProviders': _getStatsProviders().keys()},
        context_instance=RequestContext(request))


def _stats_overview_csv(tableHeadings, dictStats, keyword, year):
    '''Creates a Response with the stat data rendered as comma-separated values (CSV)'''

    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = 'attachment; filename=stats.%s.%s.csv' % (keyword, year)

    # apparently, in this loop, datetime.date objects in dictStats are automatically formatted according to ISO
    # which is 'YYYY-MM-DD' and looks good in CSV
    
    writer = csv.writer(response)
    writer.writerow(tableHeadings)
    for statRow in dictStats.itervalues():
        writer.writerow(statRow.values())

    return response


def _stats_overview_xls(tableHeadings, dictStats, keyword, year):
    '''Creates a Response with the stat data rendered in a MS Excel format'''

    response = HttpResponse(mimetype='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename=stats.%s.%s.xls' % (keyword, year)

    # init sheet
    book = xlwt.Workbook()
    sheet = book.add_sheet('%s %s' % (keyword, year))

    # write heading row
    row, col = 0, 0
    for heading in tableHeadings:
        sheet.write(row, col, heading)
        col += 1

    # stat data after that
    row, col = 1, 0
    for statRow in dictStats.itervalues():
        for stat in statRow.itervalues():
            if isinstance(stat, datetime.date):
                style = xlwt.Style.XFStyle()
                style.num_format_str = 'YYYY-MM-DD'
            elif isinstance(stat, datetime.datetime):
                style = xlwt.Style.XFStyle()
                style.num_format_str = 'YYYY-MM-DD hh:mm:ss'
            else:
                style = xlwt.Style.default_style

            sheet.write(row, col, stat, style)
            col += 1
        row += 1
        col = 0

    book.save(response)
    return response


def _getStatsProviders():
    '''Maps stat keyword to corresponding StatsProvider -- for now in a static fashion'''
    return { 'chat': ChatStatsProvider }


def _getStatsProvider(forName):
    '''find appropriate StatsProvider for given keyword'''

    forName = forName.lower()
    knownProviders = _getStatsProviders()

    if forName in knownProviders:
        return knownProviders[forName]
    else:
        return None