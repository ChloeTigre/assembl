// @flow
import React from 'react';
import { Map } from 'immutable';
import { Translate } from 'react-redux-i18n';
import range from 'lodash/range';
import classnames from 'classnames';
import { Grid, Row, Col } from 'react-bootstrap';

import Circle from '../svg/circle';
import { type TokenCategory } from '../../pages/voteSession';

type Props = {
  remainingTokensByCategory: Map<string, number>,
  sticky: boolean,
  tokenCategories: Array<?TokenCategory>
};

const getColumnSizes: Function = (numberCategoriesToDisplay) => {
  switch (numberCategoriesToDisplay) {
  case 1:
    return [12];
  case 2:
    return [6, 6];
  case 3:
    return [4, 4, 4];
  case 4:
    return [6, 6, 6, 6];
  default:
    return [12];
  }
};

const getClassNames: Function = (numberCategoriesToDisplay) => {
  switch (numberCategoriesToDisplay) {
  case 1:
    return ['left'];
  case 2:
    return ['left', 'right'];
  case 3:
    return ['left', '', 'right'];
  case 4:
    return ['left', 'right', 'left', 'right'];
  default:
    return ['left'];
  }
};

const AvailableTokens = ({ remainingTokensByCategory, sticky, tokenCategories }: Props) => {
  const columnSizes: Array<number> = getColumnSizes(tokenCategories.length);
  const columnClass: Array<string> = getClassNames(tokenCategories.length);
  return (
    <div
      className={classnames({
        'available-tokens-sticky': sticky,
        box: sticky,
        'available-tokens': !sticky,
        hidden: tokenCategories.length > 4 && sticky
      })}
    >
      <Grid fluid>
        <div className="max-container">
          <Row>
            {tokenCategories.map((category, idx) => {
              if (category) {
                const { color, id, title, totalNumber } = category;
                const remaining = remainingTokensByCategory.get(category.id);
                return (
                  <Col xs={12} md={sticky ? columnSizes[idx] : 12} key={id} className={sticky && idx % 2 !== 0 ? 'center' : ''}>
                    <div className={sticky ? `category-available-tokens ${columnClass[idx]}` : 'category-available-tokens'}>
                      <div
                        className="text"
                        style={
                          sticky && tokenCategories.length % 2 !== 0 && tokenCategories.length > 2
                            ? { maxWidth: '210px' }
                            : { minWidth: '250px' }
                        }
                      >
                        <h2 className="dark-title-2">{title}</h2>
                        <Translate value="debate.voteSession.remainingTokens" count={remaining} />
                      </div>
                      <div
                        className="tokens"
                        style={
                          sticky && tokenCategories.length % 2 !== 0 && tokenCategories.length > 2
                            ? { maxWidth: '160px' }
                            : { minWidth: '330px' }
                        }
                      >
                        {range(totalNumber).map(n => (
                          <Circle key={n + 1} size={28} strokeColor={color} fillColor={n + 1 <= remaining ? color : undefined} />
                        ))}
                      </div>
                    </div>
                    {idx !== tokenCategories.length - 1 && <div className="separator" />}
                  </Col>
                );
              }
              return null;
            })}
          </Row>
        </div>
      </Grid>
    </div>
  );
};

export default AvailableTokens;