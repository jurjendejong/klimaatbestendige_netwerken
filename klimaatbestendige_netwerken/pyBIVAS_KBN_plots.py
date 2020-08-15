from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import seaborn as sns
from matplotlib.colors import LogNorm, SymLogNorm

inputdir = Path('../1_Output_conversion/Analyse_BIVAS')
outputdir = Path('Compare scenarios')

ylim_barplots = 0

class scenarios:
    # Define all scenarios
    Q = [700, 850, 1020, 1400, 1800]

    scenarios_Q = [f'Q{s:.0f}' for s in sorted(Q)]
    Q_mapper = {k: v for k, v in zip(scenarios_Q, Q)}

    scenarios_Q_reverse = scenarios_Q[::-1]

    scenarios_Q_incl_WHO = scenarios_Q + [f'{s}_WLO2050H' for s in scenarios_Q] + ['Q1020_WLO2050L']

    Qref = 'Q1800'
    Qref_vracht = 'Q700'

class mapping:
    # Load mappings
    mappingfile = inputdir / 'land_node_mapping.pkl'
    mapping_country = pd.read_pickle(mappingfile)

    mapping_basgoed2018 = pd.read_pickle(inputdir / 'zone_node_mapping.pkl')

    nl = 'NL - Netherlands'

    mapping_node_zone = pd.concat([
        mapping_country.rename(columns={'ZoneID': 'CountryID', 'Name': 'Country'}).set_index('NodeID'),
        mapping_basgoed2018.rename(columns={'ZoneID': 'BasGoed2018ID', 'Name': 'BasGoed2018'}).set_index('NodeID')
    ], axis=1)

    mapping_zone_country = mapping_node_zone.groupby('BasGoed2018').agg(lambda x: pd.Series.mode(x)[0])['Country']

    corridorsfile = inputdir / '..' / 'Other_input' / 'corridors.xlsx'
    basgoed2018_corridor = pd.read_excel(corridorsfile).set_index('Name')

    corridor_volgorde = pd.read_excel(corridorsfile, sheet_name='Volgorde', header=None)[0].values

    basgoedzone_country_volgorde = np.append(
        sorted(mapping_zone_country[mapping_zone_country == nl].index.unique().values),
        sorted(mapping_zone_country[mapping_zone_country != nl].unique())
    )


def read_scenarios(file, scenarios, addcolumns=True, dropinfeasible=True, increaseemptytrips=True, keep_columns=None):
    def add_columns(df):
        if 'Origin_Node' in df:
            df['Origin_Country'] = mapping.mapping_node_zone.reindex(df['Origin_Node'])['Country'].values
            df['Destination_Country'] = mapping.mapping_node_zone.reindex(df['Destination_Node'])['Country'].values
        else:
            df['Origin_Country'] = mapping.mapping_node_zone.reindex(df['OriginTripEndPointNodeID'])['Country'].values
            df['Destination_Country'] = mapping.mapping_node_zone.reindex(df['DestinationTripEndPointNodeID'])['Country'].values

            df['Origin_Zone'] = mapping.mapping_node_zone.reindex(df['OriginTripEndPointNodeID'])['BasGoed2018'].values
            df['Destination_Zone'] = mapping.mapping_node_zone.reindex(df['DestinationTripEndPointNodeID'])[
                'BasGoed2018'].values

        df['Vervoerstromen'] = None
        df.loc[(df['Origin_Country'] == mapping.nl) & (df['Destination_Country'] == mapping.nl), 'Vervoerstromen'] = 'Binnenlands'
        df.loc[(df['Origin_Country'] != mapping.nl) & (df['Destination_Country'] == mapping.nl), 'Vervoerstromen'] = 'Aanvoer'
        df.loc[(df['Origin_Country'] == mapping.nl) & (df['Destination_Country'] != mapping.nl), 'Vervoerstromen'] = 'Afvoer'
        df.loc[(df['Origin_Country'] != mapping.nl) & (df['Destination_Country'] != mapping.nl), 'Vervoerstromen'] = 'Doorvoer'

        df['Origin_Corridor'] = mapping.basgoed2018_corridor.loc[df['Origin_Zone'].values]['Corridors'].values
        df['Destination_Corridor'] = mapping.basgoed2018_corridor.loc[df['Destination_Zone'].values]['Corridors'].values

        df['Origin_ZoneNLorCountry'] = df['Origin_Zone']
        buitenland = df['Origin_Country'] != mapping.nl
        df.loc[buitenland, 'Origin_ZoneNLorCountry'] = df['Origin_Country'][buitenland]

        df['Destination_ZoneNLorCountry'] = df['Destination_Zone']
        buitenland = df['Destination_Country'] != mapping.nl
        df.loc[buitenland, 'Destination_ZoneNLorCountry'] = df['Destination_Country'][buitenland]

        df = df.drop('Days', axis=1, errors='ignore')

        df = df.rename(columns={
            'appearance_types_Description': 'Vorm',
            'DateTime': 'Days',
        })

        return df

    def function_drop_infeasible(df, scenario):
        infeasible_index = pd.read_pickle('Infeasible trips/All infeasible.pkl')
        infeasible_index_Q = infeasible_index[scenario][infeasible_index[scenario]].index
        df = df.drop(infeasible_index_Q, axis=0, errors='ignore')
        return df

    from klimaatbestendige_netwerken.pyBIVAS_data_postprocessing import increase_empty_trips

    D = {}
    for s in scenarios:
        print('Loading', s)
        df = pd.read_pickle(inputdir / s / file)

        if addcolumns:
            df = add_columns(df)

        if dropinfeasible:
            df = function_drop_infeasible(df, s)

        if increaseemptytrips:
            increase_empty_trips.adjust_trips_lege_schepen(df, s)

        if keep_columns is not None:
            df = df[keep_columns]

        D[s] = df
    D = pd.concat(D, axis=1)
    D = D[scenarios]
    return D

## Plotting functions

def groupby(x, y, bins=100):
    cut, bins = pd.cut(x, bins=bins, retbins=True)
    bins_mean = (bins[:-1] + bins[1:]) / 2
    r = y.groupby(cut).describe()
    r.index = [np.round(a, 2) for a in bins_mean]
    return r


def diff_Q(df):
    df2 = df.copy()
    for c1, c2 in zip(scenarios.scenarios_Q[:-1], scenarios.scenarios_Q[1:]):
        df2[c1] = df[c1] - df[c2]
    df2 = df2[scenarios.scenarios_Q_reverse]
    return df2


def diff_Q_decreasing(df):
    df2 = df.copy()
    for c1, c2 in zip(scenarios.scenarios_Q[1:], scenarios.scenarios_Q[:-1]):
        df2[c1] = df[c1] - df[c2]
    df2 = df2[scenarios.scenarios_Q]
    return df2


def inverselegend(outside=False, **kwargs):
    if outside:
        plt.gca().legend(*map(reversed, plt.gca().get_legend_handles_labels()), loc='center left',
                         bbox_to_anchor=(1, 0.5), **kwargs)
    else:
        plt.gca().legend(*map(reversed, plt.gca().get_legend_handles_labels()), **kwargs)


def vaarweg_plot_diepgang(D, Q, figuredir=Path('.')):
    bins = np.arange(0, 5.01, 0.10)
    plotdata = D.xs('Depth__m', axis=1, level=1).copy()

    plotdata['Maximaal'] = D[(scenarios.Qref, 'Maximale_diepgang')]
    plotdata['Ledig'] = D[(scenarios.Qref, 'Ledige_diepgang')]

    s = [scenarios.Qref, Q]

    f, ax = plt.subplots(figsize=(8, 4))
    plotdata[s].plot.hist(bins=bins, histtype='step', lw=2, ax=ax, ls='-')
    plotdata[['Maximaal', 'Ledig']].plot.hist(bins=bins, histtype='step', lw=1.5, figsize=(8, 4), ls=':', ax=ax)

    plt.ylabel('Aantal schepen')
    plt.xlabel('Diepgang (m)')
    plt.grid()
    plt.title('Effect van lagere waterstanden op de diepgang')
    plotdata.to_csv(figuredir / f'Diepgang.csv')
    plt.savefig(figuredir / f'Diepgang.png', dpi=300, bbox_inches='tight')
    plt.close()


def vaarweg_plot_beladingsgraad(D, branchname='', figuredir=Path('.')):
    DD = {}
    for s in scenarios.scenarios_Q:
        DD[s] = D[s].groupby('Vorm')['Beladingsgraad'].quantile([0.05, 0.25, 0.50, 0.75, 0.95])

    DD = pd.concat(DD, axis=1).rename(scenarios.Q_mapper, axis=1).sort_index(axis=1)
    DD.columns = DD.columns.astype(int)

    for v in DD.index.levels[0]:
        if v == 'Leeg': continue
        DD.loc[v].boxplot(positions=DD.columns, widths=100, figsize=(4, 4), )
        plt.xlabel('Afvoer Lobith ($m^3/s$)')
        plt.ylabel('Beladingsgraad')
        plt.title(f'{v} - {branchname}')
        plt.ylim(0, 1)
        plt.xlim(600, 2100)
        DD.to_csv(figuredir / f'Beladingsgraad_{v}.csv')
        plt.savefig(figuredir / f'Beladingsgraad_{v}.png', dpi=300, bbox_inches='tight')
        plt.close()


def plot_groupby_ship_types(D, figuredir=Path('.')):
    ships_with_largest_tonkm = D[scenarios.Qref].groupby(['ship_types_Label'])['Totale TonKM (TONKM)'].sum().sort_values(
        ascending=False).index[:20]

    plotdata = {}
    for c in scenarios.scenarios_Q:
        plotdata[c] = D[c]
        plotdata[c] = plotdata[c].groupby(['ship_types_Label']).sum()['Totale Variabele Vaarkosten (EUR)']

    plotdata = pd.concat(plotdata, axis=1, sort=True) / 1e6
    plotdata = plotdata.loc[ships_with_largest_tonkm]

    plotdata = diff_Q(plotdata)

    # Toevoegen vaste vaarkosten
    vast = D[scenarios.Qref].groupby(['ship_types_Label']).sum()['Totale Vaste Vaarkosten (EUR)'] / 1e6
    plotdata.insert(0, 'Vaste kosten', vast)
    #     plotdata[Qref] = plotdata[Qref] - vast

    ax = plotdata.plot.bar(width=0.8, zorder=3, figsize=(8, 4), stacked=True, cmap='viridis', edgecolor='w',
                           linewidth=0.3)
    ax.ticklabel_format(style='plain', axis='y')
    plt.grid()
    plt.xlabel('')
    inverselegend()
    plt.ylabel('Vaarkosten (mln EUR)')
    plt.ylim(bottom=ylim_barplots)
    plotdata.to_csv(figuredir / 'Vaarkosten_per_scheepstype.csv')
    plt.savefig(figuredir / 'Vaarkosten_per_scheepstype.png', dpi=300, bbox_inches='tight')
    plt.close()


def plot_groupby_ship_types_eurtonkm(D, figuredir=Path('.')):
    ships_with_largest_tonkm = D[scenarios.Qref].groupby(['ship_types_Label'])['Totale TonKM (TONKM)'].sum().sort_values(
        ascending=False).index[:20]

    plotdata = {}
    for c in scenarios.scenarios_Q:
        plotdata[c] = D[c]
        plotdata[c] = plotdata[c][plotdata[c]['Vorm'] != 'Leeg']
        plotdata[c] = plotdata[c].groupby(['ship_types_Label']).sum()
        plotdata[c] = plotdata[c][plotdata[c]['Totale TonKM (TONKM)'] > 0]
        plotdata[c] = plotdata[c]['Totale Vaarkosten (EUR)'] / plotdata[c]['Totale TonKM (TONKM)']

    plotdata = pd.concat(plotdata, axis=1, sort=True)
    plotdata = plotdata.reindex(ships_with_largest_tonkm, fill_value=0)

    plotdata = diff_Q(plotdata)

    ax = plotdata.plot.bar(width=0.8, zorder=3, figsize=(8, 4), stacked=True, cmap='viridis', edgecolor='w',
                           linewidth=0.3)
    ax.ticklabel_format(style='plain', axis='y')
    plt.grid()
    plt.xlabel('')
    inverselegend()
    plt.ylabel('Vaarkosten per tonkm (EUR)')
    plt.ylim(bottom=ylim_barplots)
    plotdata.to_csv(figuredir / 'Vaarkosten_per_tonkm_per_scheepstype.csv')
    plt.savefig(figuredir / 'Vaarkosten_per_tonkm_per_scheepstype.png', dpi=300, bbox_inches='tight')
    plt.close()


def plot_groupby_ship_types_vracht(D, figuredir=Path('.')):
    ships_with_largest_tonkm = D[scenarios.Qref].groupby(['ship_types_Label'])['Totale TonKM (TONKM)'].sum().sort_values(
        ascending=False).index[:20]

    plotdata = {}
    for c in scenarios.scenarios_Q:
        plotdata[c] = D[c]
        plotdata[c] = plotdata[c].groupby(['ship_types_Label']).sum()['Totale Vracht (ton)']

    plotdata = pd.concat(plotdata, axis=1, sort=True) / 1e6
    plotdata = plotdata.loc[ships_with_largest_tonkm]

    plotdata = diff_Q_decreasing(plotdata)

    ax = plotdata.plot.bar(width=0.8, zorder=3, figsize=(8, 4), stacked=True, cmap='plasma', edgecolor='w',
                           linewidth=0.3)
    ax.ticklabel_format(style='plain', axis='y')
    plt.grid()
    plt.xlabel('')
    inverselegend()
    plt.ylabel('Vracht (mln ton)')
    plt.ylim(bottom=ylim_barplots)
    plotdata.to_csv(figuredir / 'Vaarkosten_per_scheepstype_vracht.csv')
    plt.savefig(figuredir / 'Vaarkosten_per_scheepstype_vracht.png', dpi=300, bbox_inches='tight')
    plt.close()


def plot_groupby_vorm(D, yvariable='Totale Variabele Vaarkosten (EUR)', figuredir=Path('.')):
    plotdata = {}
    for c in scenarios.scenarios_Q:
        plotdata[c] = D[c]
        plotdata[c] = plotdata[c].groupby(['Vorm']).sum()[yvariable]

    plotdata = pd.concat(plotdata, axis=1) / 1e6
    #     plotdata.sort_values(Qref, inplace=True, ascending=False)

    plotdata = diff_Q(plotdata)

    # Toevoegen vaste vaarkosten
    if yvariable == 'Totale Variabele Vaarkosten (EUR)':
        vast = D[scenarios.Qref].groupby(['Vorm']).sum()['Totale Vaste Vaarkosten (EUR)'] / 1e6
        plotdata.insert(0, 'Vaste kosten', vast)
    #         plotdata[Qref] = plotdata[Qref] - vast

    ax = plotdata.plot.bar(width=0.8, zorder=3, figsize=(2, 4), stacked=True, cmap='viridis', edgecolor='w',
                           linewidth=0.3)
    ax.ticklabel_format(style='plain', axis='y')
    plt.grid()
    plt.xlabel('')
    plt.ylim(bottom=ylim_barplots)
    inverselegend(outside=True)
    if yvariable == 'Totale Variabele Vaarkosten (EUR)':
        plt.ylabel('Vaarkosten (mln EUR)')
        plotdata.to_csv(figuredir / 'Vaarkosten_per_vorm.csv')
        plt.savefig(figuredir / 'Vaarkosten_per_vorm.png', dpi=300, bbox_inches='tight')
    elif yvariable == 'Aantal Vaarbewegingen (-)':
        plt.ylabel('Aantal vaarbewegingen (mln)')
        plotdata.to_csv(figuredir / 'Vaarbewegingen_per_vorm.csv')
        plt.savefig(figuredir / 'Vaarbewegingen_per_vorm.png', dpi=300, bbox_inches='tight')
    plt.close()


def plot_groupby_vorm_vracht(D, figuredir=Path('.')):
    plotdata = {}
    for c in scenarios.scenarios_Q:
        plotdata[c] = D[c]
        plotdata[c] = plotdata[c].groupby(['Vorm']).sum()['Totale Vracht (ton)']

    plotdata = pd.concat(plotdata, axis=1) / 1e6
    #     plotdata.sort_values(Qref, inplace=True, ascending=False)

    plotdata = diff_Q_decreasing(plotdata)

    ax = plotdata.plot.bar(width=0.8, zorder=3, figsize=(2, 4), stacked=True, cmap='plasma', edgecolor='w',
                           linewidth=0.3)
    ax.ticklabel_format(style='plain', axis='y')
    plt.grid()
    plt.xlabel('')
    plt.ylim(bottom=ylim_barplots)
    inverselegend(outside=True)
    plt.ylabel('Vracht (mln ton)')
    plotdata.to_csv(figuredir / 'Vaarkosten_per_vorm_vracht.csv')
    plt.savefig(figuredir / 'Vaarkosten_per_vorm_vracht.png', dpi=300, bbox_inches='tight')
    plt.close()


def plot_groupby_NSTR(D, figuredir=Path('.')):
    plotdata = {}
    for c in scenarios.scenarios_Q:
        plotdata[c] = D[c]
        plotdata[c] = plotdata[c].groupby(['NSTR']).sum()['Totale Variabele Vaarkosten (EUR)']

    plotdata = pd.concat(plotdata, axis=1) / 1e6
    #     plotdata.sort_values(Qref, inplace=True, ascending=False)

    plotdata = diff_Q(plotdata)

    # Toevoegen vaste vaarkosten
    vast = D[scenarios.Qref].groupby(['NSTR']).sum()['Totale Vaste Vaarkosten (EUR)'] / 1e6
    plotdata.insert(0, 'Vaste kosten', vast)
    #     plotdata[Qref] = plotdata[Qref] - vast

    ax = plotdata.plot.bar(width=0.8, zorder=3, figsize=(4, 4), stacked=True, cmap='viridis', edgecolor='w',
                           linewidth=0.3)
    ax.ticklabel_format(style='plain', axis='y')
    plt.grid()
    plt.xlabel('')
    plt.ylim(bottom=ylim_barplots)
    inverselegend()
    plt.ylabel('Vaarkosten (mln EUR)')
    plotdata.to_csv(figuredir / 'Vaarkosten_per_NSTR.csv')
    plt.savefig(figuredir / 'Vaarkosten_per_NSTR.png', dpi=300, bbox_inches='tight')
    plt.close()


def plot_groupby_NSTR_vracht(D, figuredir=Path('.')):
    plotdata = {}
    for c in scenarios.scenarios_Q:
        plotdata[c] = D[c]
        plotdata[c] = plotdata[c].groupby(['NSTR']).sum()['Totale Vracht (ton)']

    plotdata = pd.concat(plotdata, axis=1) / 1e6
    #     plotdata.sort_values(Qref, inplace=True, ascending=False)

    plotdata = diff_Q_decreasing(plotdata)

    ax = plotdata.plot.bar(width=0.8, zorder=3, figsize=(4, 4), stacked=True, cmap='plasma', edgecolor='w',
                           linewidth=0.3)
    ax.ticklabel_format(style='plain', axis='y')
    plt.grid()
    plt.xlabel('')
    plt.ylim(bottom=ylim_barplots)
    inverselegend()
    plt.ylabel('Vracht (mln ton)')
    plotdata.to_csv(figuredir / 'Vaarkosten_per_NSTR_vracht.csv')
    plt.savefig(figuredir / 'Vaarkosten_per_NSTR_vracht.png', dpi=300, bbox_inches='tight')
    plt.close()


def plot_vaarkostenpertonkm(D, figuredir=Path('.')):
    x = D[scenarios.Qref]['Depth__m']
    y = (
        D[scenarios.Qref][['Totale Vaarkosten (EUR)', 'Totale Vaste Vaarkosten (EUR)', 'Totale Variabele Vaarkosten (EUR)']]).div(
        D[scenarios.Qref]['Totale TonKM (TONKM)'], axis=0)  # / D['REF']['Totale Vaarkosten (EUR)']

    # Selectie van diepgang (1 - 4 m) en geen nan, en maximale kosten 0.1 eur/tonkm
    ii = (x < 4.1) & (x >= 1.0) & (~y.isna().any(axis=1)) & ~(y.max(axis=1) > 0.1)
    x = x[ii]
    y = y[ii]

    bins = np.linspace(1 - 1 / 8, 4 + 1 / 8, int((4 - 1) / 0.25 + 2))
    r = groupby(x, y, bins=bins).swaplevel(axis=1)['50%']

    y2 = D[scenarios.scenarios_Q].xs('Totale Vaarkosten (EUR)', axis=1, level=1).div(D[scenarios.Qref]['Totale TonKM (TONKM)'], axis=0)
    y2 = diff_Q(y2)[ii]

    r2 = groupby(x, y2, bins=bins)
    r2 = r2.swaplevel(axis=1)['50%']

    vast = r['Totale Vaste Vaarkosten (EUR)']
    r2.insert(0, 'Vaste kosten', vast)
    r2[scenarios.Qref] = r2[scenarios.Qref] - vast
    plotdata = r2

    plotdata.plot.bar(stacked=True, width=0.8, zorder=3, cmap='viridis', edgecolor='w', linewidth=0.3)
    plt.ylim(bottom=0)
    plt.ylabel('Vaarkosten per TonKM (EUR)')
    plt.xlabel('Diepgang in referentie (m)')
    plt.grid()
    inverselegend(outside=True)
    plotdata.to_csv(figuredir / 'Barplot_diepgang_vaarkostenpertonkm.csv')
    plt.savefig(figuredir / 'Barplot_diepgang_vaarkostenpertonkm.png', dpi=300, bbox_inches='tight')
    plt.close()


# plot_vaarkostenpertonkm(D)

def plot_timeseries(D, figuredir=Path('.')):
    plotdata = D[scenarios.Qref].groupby('Days')['Aantal Vaarbewegingen (-)'].sum()
    plotdata.index = (plotdata.index - pd.Timedelta('4y')).round('d')
    plotdata.plot()
    gemiddelde = plotdata.mean()
    plt.axhline(gemiddelde, c='red', ls=':')
    plt.grid()
    plt.ylabel('Aantal vaarbewegingen')
    plt.xlabel('')
    plt.savefig(figuredir / 'Tijdserie_vaarbewegingen.png', dpi=300, bbox_inches='tight')
    plt.close()

    plotdata.index = plotdata.index.dayofweek

    plotdata = plotdata.reset_index().groupby('Days').mean()
    plotdata.index = ['Ma', 'Di', 'Wo', 'Do', 'Vr', 'Za', 'Zo']

    plotdata['Aantal Vaarbewegingen (-)'].plot.bar(figsize=(3, 4), zorder=3, width=0.8)
    plt.axhline(gemiddelde, c='red', ls=':', zorder=5)
    plt.grid()
    plt.ylabel('Aantal vaarbewegingen')
    plt.savefig(figuredir / 'TijdserieWeek_vaarbewegingen.png', dpi=300, bbox_inches='tight')
    plt.close()


def plot_basgoed(D, t, figuredir=Path('.')):
    T_dict = {'Origin': "Herkomst", 'Destination': 'Bestemming'}
    T = T_dict[t]

    D_zone = {}
    # Read
    for s in scenarios.scenarios_Q:
        D_zone[s] = D[s][D[s][f'{t}_Country'] == mapping.nl].groupby(f'{t}_Zone')['Totale Vaarkosten (EUR)'].sum()
    D_zone = pd.concat(D_zone, axis=1, sort=False)
    # D_zone

    plotdata = diff_Q(D_zone)
    plotdata = plotdata / 1e6

    # Toevoegen vaste vaarkosten
    vast = D[scenarios.Qref][D[scenarios.Qref][f'{t}_Country'] == mapping.nl].groupby(f'{t}_Zone')['Totale Vaste Vaarkosten (EUR)'].sum() / 1e6
    plotdata.insert(0, 'Vaste kosten', vast)
    plotdata[scenarios.Qref] = plotdata[scenarios.Qref] - vast

    plotdata.plot.bar(width=0.8, figsize=(12, 4), zorder=3, stacked=True, cmap='viridis', edgecolor='w', linewidth=0.3)
    plt.ylabel('Vaarkosten (mln EUR)')
    plt.xlabel('')
    plt.grid()
    plt.ylim(bottom=ylim_barplots)
    inverselegend()
    plt.title(f'Vaarkosten per regio van {T}')
    plotdata.to_csv(figuredir / f'Toename vaarkosten per {T}.csv')
    plt.savefig(figuredir / f'Toename vaarkosten per {T}.png', bbox_inches='tight', dpi=300)
    plt.close()


def plot_basgoed_vracht(D, t, figuredir=Path('.')):
    T_dict = {'Origin': "Herkomst", 'Destination': 'Bestemming'}
    T = T_dict[t]

    D_zone = {}
    # Read
    for s in scenarios.scenarios_Q:
        D_zone[s] = D[s][D[s][f'{t}_Country'] == mapping.nl].groupby(f'{t}_Zone')['Totale Vracht (ton)'].sum()
    D_zone = pd.concat(D_zone, axis=1, sort=False)

    plotdata = diff_Q_decreasing(D_zone)
    plotdata = plotdata / 1e6
    plotdata.plot.bar(width=0.8, figsize=(12, 4), zorder=3, stacked=True, cmap='plasma', edgecolor='w', linewidth=0.3)
    plt.ylabel('Vracht (mln ton)')
    plt.xlabel('')
    plt.grid()
    plt.ylim(bottom=ylim_barplots)
    inverselegend()
    plt.title(f'Vracht per regio van {T}')
    plotdata.to_csv(figuredir / f'Toename vaarkosten per {T}_vracht.csv')
    plt.savefig(figuredir / f'Toename vaarkosten per {T}_vracht.png', bbox_inches='tight', dpi=300)
    plt.close()


def plot_country(D, t, figuredir=Path('.')):
    T_dict = {'Origin': "Herkomst", 'Destination': 'Bestemming'}
    T = T_dict[t]

    D_zone = {}
    # Read
    for s in scenarios.scenarios_Q:
        D_zone[s] = D[s].groupby(f'{t}_Country')['Totale Variabele Vaarkosten (EUR)'].sum()
    D_zone = pd.concat(D_zone, axis=1, sort=False)

    plotdata = diff_Q(D_zone)

    # Toevoegen vaste vaarkosten
    vast = D[scenarios.Qref].groupby(f'{t}_Country')['Totale Vaste Vaarkosten (EUR)'].sum()
    plotdata.insert(0, 'Vaste kosten', vast)
    #     plotdata[Qref] = plotdata[Qref] - vast

    plotdata = plotdata.sort_values(by=scenarios.Qref, ascending=False) / 1e6
    plotdata = plotdata.iloc[:5]
    plotdata.plot.bar(zorder=3, width=0.8, stacked=True, cmap='viridis', edgecolor='w', linewidth=0.3)
    plt.ylabel('Vaarkosten (mln EUR)')
    plt.xlabel('')
    plt.grid()
    inverselegend()
    plt.ylim(bottom=ylim_barplots)
    plt.title(f'Vaarkosten per land van {T}')
    plotdata.to_csv(figuredir / f'Toename vaarkosten per land_{T}.csv')
    plt.savefig(figuredir / f'Toename vaarkosten per land_{T}.png', bbox_inches='tight', dpi=300)
    plt.close()


def plot_country_vracht(D, t, figuredir=Path('.')):
    T_dict = {'Origin': "Herkomst", 'Destination': 'Bestemming'}
    T = T_dict[t]

    D_zone = {}
    # Read
    for s in scenarios.scenarios_Q:
        D_zone[s] = D[s].groupby(f'{t}_Country')['Totale Vracht (ton)'].sum()
    D_zone = pd.concat(D_zone, axis=1, sort=False)

    plotdata = diff_Q_decreasing(D_zone)

    plotdata = plotdata.sort_values(by=scenarios.Qref_vracht, ascending=False) / 1e6
    plotdata = plotdata.iloc[:5]
    plotdata.plot.bar(zorder=3, width=0.8, stacked=True, cmap='plasma', edgecolor='w', linewidth=0.3)
    plt.ylabel('Vracht (mln ton)')
    plt.xlabel('')
    plt.grid()
    inverselegend()
    plt.ylim(bottom=ylim_barplots)
    plt.title(f'Vracht per land van {T}')
    plotdata.to_csv(figuredir / f'Toename vaarkosten per land_{T}_vracht.csv')
    plt.savefig(figuredir / f'Toename vaarkosten per land_{T}_vracht.png', bbox_inches='tight', dpi=300)
    plt.close()


def plot_vervoerstromen(D, figuredir=Path('.')):
    DD = {}
    for s in D.columns.levels[0]:
        DD[s] = D[s].groupby('Vervoerstromen').sum()['Totale Variabele Vaarkosten (EUR)']
    DD = pd.concat(DD, axis=1)

    plotdata = diff_Q(DD) / 1e6

    # Toevoegen vaste vaarkosten
    vast = D[scenarios.Qref].groupby('Vervoerstromen')['Totale Vaste Vaarkosten (EUR)'].sum() / 1e6
    plotdata.insert(0, 'Vaste kosten', vast)
    #     plotdata[Qref] = plotdata[Qref] - vast

    plotdata.plot.bar(zorder=3, figsize=(4, 4), width=0.8, stacked=True, cmap='viridis', edgecolor='w', linewidth=0.3)
    plt.grid()
    plt.ylabel('Vaarkosten (mln EUR)')
    plt.ylim(bottom=ylim_barplots)
    inverselegend(outside=True)
    plotdata.to_csv(figuredir / 'Vervoersstromen.csv')
    plt.savefig(figuredir / 'Vervoersstromen.png', dpi=300, bbox_inches='tight')
    plt.close()


def plot_vervoerstromen_vracht(D, figuredir=Path('.')):
    DD = {}
    for s in D.columns.levels[0]:
        DD[s] = D[s].groupby('Vervoerstromen').sum()['Totale Vracht (ton)']
    DD = pd.concat(DD, axis=1)

    plotdata = diff_Q_decreasing(DD) / 1e6
    plotdata.plot.bar(zorder=3, figsize=(4, 4), width=0.8, stacked=True, cmap='plasma', edgecolor='w', linewidth=0.3)
    plt.grid()
    plt.ylabel('Vracht (mln ton)')
    inverselegend(outside=True)
    plotdata.to_csv(figuredir / 'Vervoersstromen_Vracht.csv')
    plt.savefig(figuredir / 'Vervoersstromen_Vracht.png', dpi=300, bbox_inches='tight')
    plt.close()


def plot_corridor(D, figuredir=Path('.')):
    heatmapdir = figuredir / 'heatmaps'
    heatmapdir.mkdir(exist_ok=True)

    cc = ['Totale Vaarkosten (EUR)', 'Totale TonKM (TONKM)', 'Totale Reistijd (min)', 'Totale Vracht (ton)',
          'Totale TEU (-)', 'Aantal Vaarbewegingen (-)']

    DD = {}
    for s in D.columns.levels[0]:
        DD[s] = D[s].groupby(['Origin_Corridor', 'Destination_Corridor'])[cc].sum()
        DD[s] = DD[s].unstack().fillna(value=0)
    DD = pd.concat(DD, axis=1)

    for c in cc:

        plotdata = DD[(scenarios.Qref, c)]
        plotdata = plotdata[mapping.corridor_volgorde].loc[mapping.corridor_volgorde]
        if plotdata.max().max() > 1e6:
            plotdata = plotdata / 1e6
            c = c.replace('(', '(mln ')
        elif plotdata.max().max() > 1e3:
            plotdata = plotdata / 1e3
            c = c.replace('(', '(x1000 ')

        f, ax = plt.subplots(figsize=(8, 7))
        sns.heatmap(plotdata.T, cmap='Blues', annot=True, fmt='.0f', ax=ax, norm=SymLogNorm(1), cbar=False)
        plt.xlabel('Herkomst')
        plt.ylabel('Bestemming')
        plt.axhline(7, color='k', lw=1)
        plt.axvline(7, color='k', lw=1)
        plt.title(c)
        plotdata.to_csv(heatmapdir / f'Heatmap_{c}.csv')
        plt.savefig(heatmapdir / f'Heatmap_{c}.png', dpi=300, bbox_inches='tight')
        plt.close()

    for Q in scenarios.scenarios_Q[:-1]:
        for c in cc:
            plotdata = DD[(Q, c)] - DD[(scenarios.Qref, c)]
            plotdata = plotdata[mapping.corridor_volgorde].loc[mapping.corridor_volgorde]
            if plotdata.max().max() > 1e6:
                plotdata = plotdata / 1e6
                c = c.replace('(', '(mln ')
            elif plotdata.max().max() > 1e3:
                plotdata = plotdata / 1e3
                c = c.replace('(', '(x1000 ')

            f, ax = plt.subplots(figsize=(8, 7))
            sns.heatmap(plotdata.T, cmap='Reds', annot=True, fmt='.0f', ax=ax, norm=SymLogNorm(1), cbar=False)
            plt.xlabel('Herkomst')
            plt.ylabel('Bestemming')
            plt.axhline(7, color='k', lw=1)
            plt.axvline(7, color='k', lw=1)
            plt.title(f'Toename {c}')
            plotdata.to_csv(heatmapdir / f'Heatmap_change_{Q}_{c}.csv')
            plt.savefig(heatmapdir / f'Heatmap_change_{Q}_{c}.png', dpi=300, bbox_inches='tight')
            plt.close()


def plot_corridor_zones(D, figuredir=Path('.')):
    heatmapdir = figuredir / 'heatmaps'
    heatmapdir.mkdir(exist_ok=True)

    cc = ['Totale Vaarkosten (EUR)', 'Totale TonKM (TONKM)', 'Totale Reistijd (min)', 'Totale Vracht (ton)',
          'Totale TEU (-)']

    DD = {}
    for s in D.columns.levels[0]:
        DD[s] = D[s].groupby(['Origin_ZoneNLorCountry', 'Destination_ZoneNLorCountry'])[cc].sum()
        DD[s] = DD[s].unstack().fillna(value=0)
    DD = pd.concat(DD, axis=1)

    def plot_heatmap_corridor(plotdata, c, figsize=(15, 12), cmap='Blues'):
        if plotdata.max().max() > 10e9:
            plotdata = plotdata / 1e9
            c = c.replace('(', '(mld ')
        elif plotdata.max().max() > 1e6:
            plotdata = plotdata / 1e6
            c = c.replace('(', '(mln ')
        elif plotdata.max().max() > 1e3:
            plotdata = plotdata / 1e3
            c = c.replace('(', '(x1000 ')

        f, ax = plt.subplots(figsize=figsize)
        sns.heatmap(plotdata.T, cmap=cmap, annot=True, fmt='.0f', ax=ax, norm=SymLogNorm(1), cbar=False)
        plt.xlabel('Herkomst')
        plt.ylabel('Bestemming')
        plt.title(c)

    for c in cc:

        plotdata = DD[(scenarios.Qref, c)]
        plotdata = plotdata.reindex(index=mapping.basgoedzone_country_volgorde, columns=mapping.basgoedzone_country_volgorde,
                                    fill_value=0)
        plotdata = plotdata.loc[
            plotdata.sum(axis=1) > plotdata.sum(axis=1).sort_values().iloc[-30], plotdata.sum(axis=0) >
            plotdata.sum(axis=0).sort_values().iloc[-30]]

        plot_heatmap_corridor(plotdata, c, figsize=(15, 12), cmap='Blues')
        plotdata.to_csv(heatmapdir / f'Heatmap_zones_{c}.csv')
        plt.savefig(heatmapdir / f'Heatmap_zones_{c}.png', dpi=300, bbox_inches='tight')
        plt.close()

        plotdata = DD[(scenarios.Qref, c)]
        plotdata = plotdata.reindex(index=mapping.basgoedzone_country_volgorde, columns=mapping.basgoedzone_country_volgorde,
                                    fill_value=0)
        plotdata = plotdata.loc[plotdata.sum(axis=1) > 0, plotdata.sum(axis=0) > 0]

        plot_heatmap_corridor(plotdata, c, figsize=(30, 25), cmap='Blues')
        plotdata.to_csv(heatmapdir / f'Heatmap_zonesL_{c}.csv')
        plt.savefig(heatmapdir / f'Heatmap_zonesL_{c}.png', dpi=300, bbox_inches='tight')
        plt.close()

        for Q in scenarios.scenarios_Q[:-1]:
            plotdata = DD[(Q, c)] - DD[(scenarios.Qref, c)]
            plotdata = plotdata.reindex(index=mapping.basgoedzone_country_volgorde, columns=mapping.basgoedzone_country_volgorde,
                                        fill_value=0)
            plotdata = plotdata.loc[
                plotdata.sum(axis=1) > plotdata.sum(axis=1).sort_values().iloc[-30], plotdata.sum(axis=0) >
                plotdata.sum(axis=0).sort_values().iloc[-30]]

            plot_heatmap_corridor(plotdata, c, figsize=(15, 12), cmap='Reds')
            plotdata.to_csv(heatmapdir / f'Heatmap_zones_change_{Q}_{c}.csv')
            plt.savefig(heatmapdir / f'Heatmap_zones_change_{Q}_{c}.png', dpi=300, bbox_inches='tight')
            plt.close()

            plotdata = DD[(Q, c)] - DD[(scenarios.Qref, c)]
            plotdata = plotdata.reindex(index=mapping.basgoedzone_country_volgorde, columns=mapping.basgoedzone_country_volgorde,
                                        fill_value=0)
            plotdata = plotdata.loc[plotdata.sum(axis=1) > 0, plotdata.sum(axis=0) > 0]

            plot_heatmap_corridor(plotdata, c, figsize=(30, 25), cmap='Reds')
            plotdata.to_csv(heatmapdir / f'Heatmap_zonesL_change_{Q}_{c}.csv')
            plt.savefig(heatmapdir / f'Heatmap_zonesL_change_{Q}_{c}.png', dpi=300, bbox_inches='tight')
            plt.close()