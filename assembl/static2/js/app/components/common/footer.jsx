// @flow
import React from 'react';
import { Link } from 'react-router';
import { Translate } from 'react-redux-i18n';
import { Grid } from 'react-bootstrap';
import { connect } from 'react-redux';
import { graphql, compose } from 'react-apollo';

import { get } from '../../utils/routeMap';
import manageErrorAndLoading from '../../components/common/manageErrorAndLoading';
import TabsConditionQuery from '../../graphql/TabsConditionQuery.graphql';

type Props = {
  assemblVersion: string,
  debateData: DebateData,
  hasLegalNotice: boolean,
  hasTermsAndConditions: boolean,
  hasCookiesPolicy: boolean,
  hasPrivacyPolicy: boolean,
  hasUserGuidelines: boolean,
  lang: string
};

const Footer = ({
  assemblVersion,
  debateData,
  hasLegalNotice,
  hasTermsAndConditions,
  hasCookiesPolicy,
  hasPrivacyPolicy,
  hasUserGuidelines,
  lang
}: Props) => {
  const { socialMedias, footerLinks } = debateData;
  const slug = { slug: debateData.slug };
  return (
    <Grid fluid className="background-dark relative" id="footer">
      <div className="max-container">
        <div className={socialMedias ? 'footer' : 'footer margin-l'}>
          {socialMedias && (
            <div>
              <p>
                <Translate value="footer.socialMedias" />
              </p>
              <div className="social-medias">
                {socialMedias.map((sMedia, index) => (
                  <Link to={sMedia.url} target="_blank" key={index}>
                    <i className={`assembl-icon-${sMedia.name}-circle`} />
                  </Link>
                ))}
              </div>
            </div>
          )}
          {footerLinks && (
            <div className="custom-links">
              {footerLinks.map((footerLink, index) => (
                <div className="inline margin-m" key={`fl-${index}`}>
                  <Link to={footerLink.url} target="_blank">
                    {footerLink.titleEntries[lang]}
                  </Link>
                </div>
              ))}
            </div>
          )}
          <div className="footer-links">
            <div className="copyright">
              ©{' '}
              <Link to="http://assembl.bluenove.com/" target="_blank">
                Assembl
              </Link>{' '}
              powered by{' '}
              <Link to="http://bluenove.com/" target="_blank">
                bluenove
              </Link>
            </div>
            <div className="terms">
              {hasTermsAndConditions && (
                <div className="terms-of-use">
                  <Link to={`${get('terms', slug)}`}>
                    <Translate value="footer.terms" />
                  </Link>
                </div>
              )}
              {hasLegalNotice && (
                <div className="legal-notice">
                  {hasTermsAndConditions ? <span className="small-hyphen-padding"> &mdash; </span> : null}
                  <Link to={`${get('legalNotice', slug)}`}>
                    <Translate value="footer.legalNotice" />
                  </Link>
                </div>
              )}
            </div>
            <div className="terms">
              {hasCookiesPolicy && (
                <div className="cookie-policy">
                  <Link to={`${get('cookiesPolicy', slug)}`}>
                    <Translate value="footer.cookiePolicy" />
                  </Link>
                </div>
              )}
              {hasPrivacyPolicy && (
                <div className="privacy-policy">
                  {hasCookiesPolicy ? <span className="small-hyphen-padding"> &mdash; </span> : null}
                  <Link to={`${get('privacyPolicy', slug)}`}>
                    <Translate value="footer.privacyPolicy" />
                  </Link>
                </div>
              )}
              {hasUserGuidelines && (
                <div className="user-guidelines">
                  {hasPrivacyPolicy || hasCookiesPolicy ? <span className="small-hyphen-padding"> &mdash; </span> : null}
                  <Link to={`${get('userGuidelines', slug)}`}>
                    <Translate value="footer.userGuidelines" />
                  </Link>
                </div>
              )}
            </div>
            {assemblVersion && <div className="assembl-version">v{assemblVersion}</div>}
          </div>
        </div>
      </div>
    </Grid>
  );
};

const mapStateToProps = state => ({
  assemblVersion: state.context.assemblVersion,
  debateData: state.debate.debateData,
  lang: state.i18n.locale
});

const withData = graphql(TabsConditionQuery, {
  props: ({ data }) => ({
    ...data
  })
});

export default compose(connect(mapStateToProps), withData, manageErrorAndLoading({ displayLoader: false }))(Footer);