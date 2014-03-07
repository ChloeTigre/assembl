define(['backbone', 'underscore', 'moment', 'ckeditor', 'app', 'models/message', 'i18n'],
function(Backbone, _, Moment, ckeditor, app, Message, i18n){
    'use strict';

    var MIN_TEXT_TO_TOOLTIP = 5,
        TOOLTIP_TEXT_LENGTH = 10;

    /**
     * @class views.MessageView
     */
    var MessageView = Backbone.View.extend({
        /**
         * @type {String}
         */
        tagName: 'div',

        /**
         * @type {String}
         */
        className: 'message',

        /**
         * Flags if it is selecting a text or not
         * @type {Boolean}
         */
        isSelecting: true,

        /**
         * @init
         * @param {MessageModel} obj the model
         * @param {Array[boolean]} last_sibling_chain which of the view's ancestors
         *   are the last child of their respective parents.
         */
        initialize: function(obj){
            this.model.on('change:isSelected', this.onIsSelectedChange, this);
            this.model.on('replaced', this.onReplaced, this);
            this.model.on('showBody', this.onShowBody, this);
            this.viewStyle = "viewStyleTitleOnly";
        },

        /**
         * The thread message template
         * @type {_.template}
         */
        template: app.loadTemplate('message'),

        /**
         * The lastest annotation created by annotator
         * @type {Annotation}
         */
        currentAnnotation: null,

        /**
         * The render
         * @return {MessageView}
         */
        render: function(){
            app.trigger('render');
            var data = this.model.toJSON(),
            children,
            level;
            level = this.currentLevel !== null ? this.currentLevel : 1;
            if( ! _.isUndefined(level) ){
                this.currentLevel = level;
            }

            this.setViewStyle(this.viewStyle);
                
            data['id'] = data['@id'];
            data['date'] = app.formatDate(data.date);
            data['creator'] = this.model.getCreator();
            data['viewStyle'] = this.viewStyle;
            // Do NOT change this, it's the message id stored in the database 
            // by annotator when storing message annotations
            // It has to contain ONLY raw content of the message provided by the
            // database for annotator to parse it back properly
            data['messageBodyId'] = app.ANNOTATOR_MESSAGE_BODY_ID_PREFIX + data['@id'];
            
            this.$el.attr("id","message-"+ data['@id']);
                if (this.model.get('read')) {
                    this.$el.addClass('read');
                } else {
                    this.$el.addClass('unread');
                }

            this.$el.html( this.template(data) );

            app.initClipboard();

            return this;
        },

        /**
         * Hide the selection tooltip
         */
        hideTooltip: function(){
            app.selectionTooltip.hide();
        },

        /**
         * Shows the selection tooltip
         * @param  {number} x
         * @param  {number} y
         * @param  {string} text
         */
        showTooltip: function(x, y, text){
            var marginLeft = app.selectionTooltip.width() / -2,
                segment = text;

            text = text.substr(0, TOOLTIP_TEXT_LENGTH) + '...' + text.substr( - TOOLTIP_TEXT_LENGTH );

            app.selectionTooltip
              .show()
              .attr('data-segment', segment)
              .text(text)
              .css({ top: y, left: x, 'margin-left': marginLeft });
        },

        /**
         *  Focus on the reply box, and open it if closed
         **/
        focusReplyBox: function(){
            this.openReplyBox();

            var that = this;
            window.setTimeout(function(){
                that.$('.message-textarea').focus();
            }, 100);
        },
        
        /**
         *  Opens the reply box the reply button
         */
        openReplyBox: function(){
            this.$('.message-replybox').show();
        },

        /**
         *  Closes the reply box
         */
        closeReplyBox: function(){
            this.$('.message-replybox').hide();
            this.$('.message-replybox-buttons').hide();
        },
        
        /**
         *  Closes the reply box and shows the reply button
         */
        showReplyBoxButtons: function(){
            this.$('.message-replybox-buttons').show();
        },
                
        /**
         * Sends the message to the server
         */
        onSendMessageButtonClick: function(ev){
            var btn = $(ev.currentTarget),
                that = this,
                btn_original_text = btn.text(),
                reply_message_id = null,
                message_body = this.$('.message-textarea').val(),
                success_callback = null;


            if( this.model.getId() ){
                reply_message_id = this.model.getId();
            }

            btn.text( i18n.gettext('Sending...') );
            success_callback = function(){
                btn.text(btn_original_text);
                that.closeReplyBox();
            }
            app.sendPostToServer(message_body, null, reply_message_id, null, success_callback)

        },

        /**
         * Shows the options to the selected text
         * @param  {Number} x
         * @param  {Number} y
         */
        showSelectionOptions: function(x, y){
            this.hideTooltip();

            var annotator = this.$el.closest('#messageList-list').data('annotator');
            annotator.onAdderClick.call(annotator);

            if( app.messageList.annotatorEditor ){
                app.messageList.annotatorEditor.element.css({
                    'top': y,
                    'left': x
                });
            }
        },

        events: {
            
            'click .message-subheader': 'onMessageTitleClick',
            'click .message-hoistbtn': 'onMessageHoistClick',

            //
            'focus .message-replybox': 'showReplyBoxButtons',
            'click .message-replybox-openbtn': 'focusReplyBox',
            'click .message-cancelbtn': 'closeReplyBox',
            'click .message-sendbtn': 'onSendMessageButtonClick',

            //
            'mousedown .message-body': 'startSelection',
            'mousemove .message-body': 'doTheSelection',
            'mouseleave .message-body': 'onMouseLeaveMessageBody',
            'mouseenter .message-body': 'doTheSelection',

            // menu
            'click #message-markasunread': 'markAsUnread'
        },

        
        /**
         * @event
         */
        onMessageHoistClick: function(ev){
            app.messageList.addFilterByPostId(this.model.getId());
        },
        
        /**
         * @event
         */
        onShowBody: function(){
            var read = this.model.get('read');
            
            this.setViewStyle('viewStyleFullMessage');
            
            if( read === false ){
                this.model.setRead(true);
            }
            
            this.render();
        },

        /**
         * You need to re-render after this
         */
        setViewStyle: function(style) {
            if(style == "viewStyleTitleOnly") {
                this.$el.removeClass('viewStyleFullMessage');
                this.$el.addClass('viewStyleTitleOnly');
                this.viewStyle = style;
            }
            else if(style == "viewStyleFullMessage"){
                this.$el.removeClass('viewStyleTitleOnly');
                this.$el.addClass('viewStyleFullMessage');
                this.model.set('collapsed', false);
                this.viewStyle = style;
            } else {
                console.log("unsupported view style :" +style );
            }
        },
        
        toggleViewStyle: function() {
            if(this.viewStyle == "viewStyleTitleOnly") {
                this.setViewStyle("viewStyleFullMessage");
            }
            else if(this.viewStyle == "viewStyleFullMessage"){
                this.setViewStyle("viewStyleTitleOnly");
            }
        },
        /**
         * @event
         */
        onMessageTitleClick: function(ev){
            if( ev ){
                // Avoiding collapse if clicked on the link
                if( ev.target.id === 'message-linkbutton' ){
                    return;
                }
            }
            this.toggleViewStyle();
            this.render();
            if (this.viewStyle == "viewStyleFullMessage") {
                this.openReplyBox();
            }
        },

        /**
         * @event
         * Starts the selection tooltip
         */
        startSelection: function(){
            this.hideTooltip();
            this.isSelecting = true;
            this.$el.addClass('is-selecting');

            var that = this;

            app.doc.one('mouseup', function(ev){
                that.stopSelection(ev);
            });
        },

        /**
         * @event
         * Does the selection
         */
        doTheSelection: function(ev){
            if( ! this.isSelecting ){
                return;
            }

            if( $(ev.target).closest('.is-selecting').length === 0 ){
                // If it isn't inside the one which started, don't show it
                return;
            }

            var selectedText = app.getSelectedText(),
                text = selectedText.getRangeAt(0).cloneContents();

            text = text.textContent || '';

            if( text.length > MIN_TEXT_TO_TOOLTIP ){
                this.showTooltip(ev.clientX, ev.clientY, text);
            } else {
                this.hideTooltip();
            }
        },

        /**
         * @event
         */
        onMouseLeaveMessageBody: function(){
            if( this.isSelecting ){
                this.hideTooltip();
            }
        },

        /**
         * @event
         */
        stopSelection: function(ev){
            var isInsideAMessage = false,
                selectedText = app.getSelectedText(),
                text = selectedText.getRangeAt(0).cloneContents();

            text = text.textContent || '';

            if( ev ){
                isInsideAMessage = $(ev.target).closest('.is-selecting').length > 0;
            }

            if( this.isSelecting && text.length > MIN_TEXT_TO_TOOLTIP && isInsideAMessage ){
                this.showSelectionOptions(ev.clientX - 50, ev.clientY);
            }

            this.isSelecting = false;
            this.$el.removeClass('is-selecting');
        },

        /**
         * @event
         */
         onReplaced: function(newObject) {
             this.setElement(newObject);
             // TODO André: also look at this one, please!
             // It will not be triggered for a while, though.
             this.render();
         },

        /**
         * Mark the current message as unread
         */
         markAsUnread: function(){
             this.model.setRead(false);
         },
         
         /**
          * Mark the current message as read
          */
         markAsRead: function(){
             this.model.setRead(true);
         }
    });


    return MessageView;

});
