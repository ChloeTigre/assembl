// @flow
import React from 'react';
/* eslint-disable import/no-extraneous-dependencies */
import { storiesOf } from '@storybook/react';
import { withKnobs, object } from '@storybook/addon-knobs';
/* eslint-enable */

import TagContainer from './tagContainer';
import type { Props as tagContainerProps } from './tagContainer';

export const defaultProps: tagContainerProps = {
  tagList: ['Habitat et SDF', 'Facilitation']
};

const playground: tagContainerProps = {
  ...defaultProps
};

storiesOf('Tag On Post|TagContainer', module)
  .addDecorator(withKnobs)
  .add('default', () => <TagContainer {...defaultProps} />)
  .add('playground', () => <TagContainer tagList={object('List of tags', playground.tagList)} />);