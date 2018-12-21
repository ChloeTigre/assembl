// @flow
import * as React from 'react';
import decorateComponentWithProps from 'decorate-component-with-props';
import { type EditorState } from 'draft-js';

// from our workspaces
import EditorUtils from 'assembl-editor-utils';

import linkConverters from './converters';
import linkStrategy, { matchesEntityType } from './linkStrategy';
import Link from './components/Link';
import LinkButton from './components/LinkButton';

type GetEditorState = void => EditorState;
type SetEditorState = EditorState => void;

export type DraftJSPluginStore = {
  getEditorState: ?GetEditorState,
  setEditorState: ?SetEditorState
};

export type Theme = {
  button: string,
  buttonWrapper: string
};

type Config = {
  closeModal: void => void,
  setModalContent: (React.Node, string) => void,
  formatLink?: string => string,
  theme?: Theme
};

export const converters = linkConverters;

export default (config: Config) => {
  const { closeModal, setModalContent, formatLink, theme } = config;

  const store = {
    getEditorState: undefined,
    setEditorState: undefined
  };

  return {
    initialize: ({ getEditorState, setEditorState }: { getEditorState: GetEditorState, setEditorState: SetEditorState }) => {
      store.getEditorState = getEditorState;
      store.setEditorState = setEditorState;
    },

    decorators: [
      {
        strategy: linkStrategy,
        matchesEntityType: matchesEntityType,
        component: decorateComponentWithProps(Link, {
          closeModal: closeModal,
          setModalContent: setModalContent,
          formatLink: formatLink
        })
      }
    ],

    LinkButton: decorateComponentWithProps(LinkButton, {
      ownTheme: theme,
      closeModal: closeModal,
      setModalContent: setModalContent,
      formatLink: formatLink,
      store: store,
      onRemoveLinkAtSelection: () => {
        const { getEditorState, setEditorState } = store;
        if (getEditorState && setEditorState) {
          setEditorState(EditorUtils.removeLinkAtSelection(getEditorState()));
        }
      }
    })
  };
};