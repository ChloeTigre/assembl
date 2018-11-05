// @flow
import React from 'react';
/* eslint-disable import/no-extraneous-dependencies */
import { storiesOf } from '@storybook/react';
import { withInfo } from '@storybook/addon-info';
import { withKnobs, text, number } from '@storybook/addon-knobs';
/* eslint-enable */

import FictionCommentHeader from '../../../../components/debate/brightMirror/fictionCommentHeader';
import type { FictionCommentHeaderProps } from '../../../../components/debate/brightMirror/fictionCommentHeader';

export const defaultFictionCommentHeader: FictionCommentHeaderProps = {
  strongTitle: 'Prenez la parole !',
  title: 'Quels sujets sont abordés dans cette fiction ?',
  imgSrc: '/static2/img/illustration-mechanisme.png',
  imgAlt: 'illustration-mechanisme',
  commentsCount: 6
};

const playground = {
  ...defaultFictionCommentHeader
};

storiesOf('FictionCommentHeader', module)
  .addDecorator(withKnobs)
  .add('default', withInfo()(() => <FictionCommentHeader {...defaultFictionCommentHeader} />))
  .add(
    'playground',
    withInfo()(() => (
      <FictionCommentHeader
        strongTitle={text('Strong title', playground.strongTitle)}
        title={text('Title', playground.title)}
        imgSrc={text('Image source', playground.imgSrc)}
        imgAlt={text('Image alt description', playground.imgAlt)}
        commentsCount={number('Number of comments', playground.commentsCount)}
      />
    ))
  );