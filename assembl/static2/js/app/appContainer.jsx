// @flow
import * as React from 'react';
import { compose, graphql, type OperationComponent } from 'react-apollo';
import { connect } from 'react-redux';
import { setLocale } from 'react-redux-i18n';
import { updateEditLocale } from './actions/adminActions';
import { setTheme } from './actions/themeActions';
import { setCookieItem, getCookieItem, convertToISO639String } from './utils/globalFunctions';
import { manageLoadingOnly } from './components/common/manageErrorAndLoading';
import { firstColor as defaultFirstColour, secondColor as defaultSecondColour } from './globalTheme';
import { availableLocales as defaultAvailableLanguages, defaultLocale } from './constants';
import CoreDiscussionPreferencesQuery from './graphql/CoreDiscussionPreferencesQuery.graphql';

type Props = {
  children: React.Node,
  discussionPreferences: CoreDiscussionPreferencesQuery,
  setDefaultLocale: Function,
  setDefaultTheme: Function,
  error: ?Object
};

const configureDefaultLocale = (availableLanguages: Array<string>, defaultLanguage: string, setDefaultLocale: Function) => {
  if (availableLanguages && availableLanguages.length === 1) {
    // The language of the debate and user will be set to the ONLY language of the debate
    setDefaultLocale(availableLanguages[0]);
  } else if (availableLanguages && availableLanguages.length > 1) {
    const cookieLanguage = getCookieItem('_LOCALE_');
    const browserLanguage = navigator.language ? convertToISO639String(navigator.language) : defaultLanguage;
    if (cookieLanguage && availableLanguages.includes(cookieLanguage)) {
      setDefaultLocale(cookieLanguage);
    } else if (browserLanguage && availableLanguages.includes(browserLanguage)) {
      setDefaultLocale(browserLanguage);
    }
  } else {
    // Pick the first language in the list of available languages, fall back to English in no case
    const lang = availableLanguages && availableLanguages.length > 0 ? availableLanguages[0] : defaultLanguage;
    setDefaultLocale(lang);
  }
};

const configureTheme = (firstColor: String, secondColor: String, setDefaultTheme: Function) => {
  setDefaultTheme(firstColor, secondColor);
};

// APPLICATION-LEVEL DEFAULT CONFIGURATIONS ARE MADE HERE
const DumbApplicationContainer = (props: Props) => {
  const { children, discussionPreferences, setDefaultLocale, setDefaultTheme, error } = props;

  // Escape out of when the /graphql route is not present. Present default values instead
  if (error && error.networkError && error.networkError.response.status === 404) {
    configureTheme(defaultFirstColour(), defaultSecondColour(), setDefaultTheme);
    configureDefaultLocale(defaultAvailableLanguages, defaultLocale, setDefaultLocale);
  } else {
    const { languages, firstColor, secondColor } = discussionPreferences;
    configureTheme(firstColor, secondColor, setDefaultTheme);
    configureDefaultLocale(languages.map(l => l.locale), defaultLocale, setDefaultLocale);
  }

  return <React.Fragment>{children}</React.Fragment>;
};

const discussionPreferencesQuery: OperationComponent<CoreDiscussionPreferencesQuery, null, Props> = graphql(
  CoreDiscussionPreferencesQuery,
  {
    props: ({ data }) => data
  }
);

const mapDispatchToProps = dispatch => ({
  setDefaultLocale: (locale) => {
    dispatch(setLocale(locale));
    dispatch(updateEditLocale(locale));
    setCookieItem('_LOCALE_', locale);
  },
  setDefaultTheme: (firstColor, secondColor) => {
    dispatch(setTheme(firstColor, secondColor));
  }
});

export default compose(discussionPreferencesQuery, connect(null, mapDispatchToProps), manageLoadingOnly)(
  DumbApplicationContainer
);